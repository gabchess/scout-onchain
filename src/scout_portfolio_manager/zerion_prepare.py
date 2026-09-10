"""Unsigned Zerion preparation, exact intent validation and durable request state.

This module cannot sign, open a review session or broadcast a transaction.
Provider envelopes remain untrusted transaction proposals even after shape checks.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

CHAINS = {
    "ethereum": (1, "ETH"),
    "base": (8453, "ETH"),
    "arbitrum": (42161, "ETH"),
    "optimism": (10, "ETH"),
    "polygon": (137, "POL"),
    "avalanche": (43114, "AVAX"),
}
TTL_SECONDS = 120
NATIVE_ADDRESS = "0x" + "e" * 40
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
AMOUNT_RE = re.compile(r"(?:0|[1-9][0-9]{0,17})(?:\.[0-9]{1,18})?")
ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]{40}")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _address(value: str) -> str:
    if not ADDRESS_RE.fullmatch(value) or int(value[2:], 16) == 0:
        raise ValueError("An explicit nonzero EVM address is required")
    return value.lower()


class PreparationIntent(BaseModel):
    """Exact EVM intent; chain and asset identities cannot be inferred from symbols."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    action: Literal["swap", "transfer", "bridge"]
    chain: str
    source_wallet: str
    asset: str
    amount: str
    target_asset: str | None = None
    destination: str | None = None
    destination_chain: str | None = None
    slippage_bps: StrictInt = Field(default=50, ge=0, le=500)

    @field_validator("chain", "destination_chain")
    @classmethod
    def chain_known(cls, value: str | None) -> str | None:
        if value is not None and value not in CHAINS:
            raise ValueError("Unsupported preparation chain; EVM allowlist only")
        return value

    @field_validator("source_wallet", "destination")
    @classmethod
    def explicit_address(cls, value: str | None) -> str | None:
        return None if value is None else _address(value)

    @field_validator("asset", "target_asset")
    @classmethod
    def exact_asset(cls, value: str | None) -> str | None:
        if value is None or value == "native":
            return value
        return _address(value)

    @field_validator("amount")
    @classmethod
    def positive_decimal(cls, value: str) -> str:
        if not AMOUNT_RE.fullmatch(value) or Decimal(value) <= 0:
            raise ValueError("Amount must be a positive decimal string, up to 18 decimal places")
        return format(Decimal(value), "f").rstrip("0").rstrip(".") if "." in value else value

    @model_validator(mode="after")
    def fields_for_action(self) -> PreparationIntent:
        if self.action == "transfer":
            if self.destination is None or self.target_asset is not None:
                raise ValueError("Transfer needs destination and no target_asset")
            if self.destination_chain is not None:
                raise ValueError("Transfer cannot change chains")
        elif self.target_asset is None:
            raise ValueError("Swap and bridge require target_asset")
        if self.action == "swap":
            if self.destination is not None or self.destination_chain is not None:
                raise ValueError("Swap returns to the source wallet on the same chain")
            if self.asset == self.target_asset:
                raise ValueError("Swap assets must differ")
        if self.action == "bridge":
            if self.destination is None or self.destination_chain is None:
                raise ValueError("Bridge needs explicit destination and destination_chain")
            if self.destination_chain == self.chain:
                raise ValueError("Bridge must change chains")
        return self

    def cli_args(self) -> list[str]:
        def token(asset: str, chain: str) -> str:
            return CHAINS[chain][1] if asset == "native" else asset

        sell = token(self.asset, self.chain)
        if self.action == "transfer":
            args = ["send", sell, self.amount, "--to", str(self.destination), "--chain", self.chain]
        elif self.action == "swap":
            args = [
                "swap",
                self.chain,
                self.amount,
                sell,
                token(str(self.target_asset), self.chain),
            ]
        else:
            args = [
                "bridge",
                self.chain,
                sell,
                self.amount,
                str(self.destination_chain),
                token(str(self.target_asset), str(self.destination_chain)),
                "--to-address",
                str(self.destination),
            ]
        return args + [
            "--address",
            self.source_wallet,
            "--slippage",
            str(Decimal(self.slippage_bps) / 100),
            "--prepare",
            "--review",
        ]


def validate_envelope(value: dict[str, Any], intent: PreparationIntent, now: datetime) -> datetime:
    """Check envelope identity/freshness; never claim to decode swap/bridge calldata."""
    if (
        value.get("kind") != "zerion-prepared-group"
        or type(value.get("version")) is not int
        or value["version"] != 1
        or value.get("ecosystem") != "evm"
        or value.get("route") != "web-app"
        or value.get("executed") is not None
    ):
        raise ValueError("Unexpected prepared envelope contract")
    if (
        value.get("chain") != intent.chain
        or value.get("address", "").lower() != intent.source_wallet
    ):
        raise ValueError("Prepared envelope wallet or chain mismatch")
    prepared = datetime.fromisoformat(value["preparedAt"].replace("Z", "+00:00"))
    if prepared.tzinfo is None or not 0 <= (now - prepared).total_seconds() <= TTL_SECONDS:
        raise ValueError("Prepared envelope timestamp is stale or invalid")
    outflows = value.get("outflows")
    if not isinstance(outflows, list) or len(outflows) != 1:
        raise ValueError("Exactly one declared outflow is required")
    flow = outflows[0]
    if flow.get("chain") != intent.chain or Decimal(str(flow.get("amount"))) != Decimal(
        intent.amount
    ):
        raise ValueError("Prepared outflow does not match intent")
    token_address = flow.get("tokenAddress")
    native = flow.get("native") is True or token_address == NATIVE_ADDRESS
    if intent.asset == "native":
        if not native:
            raise ValueError("Native asset identity is unproven")
    elif not isinstance(token_address, str) or token_address.lower() != intent.asset or native:
        raise ValueError("Prepared token identity mismatch")
    txs = value.get("transactions")
    if not isinstance(txs, list) or not 1 <= len(txs) <= 8:
        raise ValueError("Invalid transaction count")
    for entry in txs:
        tx = entry.get("evm", {})
        if (
            not tx
            or "solana" in entry
            or tx.get("from", "").lower() != intent.source_wallet
            or int(tx["chainId"], 16) != CHAINS[intent.chain][0]
            or any(k in tx for k in ("nonce", "r", "s", "v", "raw", "signature"))
        ):
            raise ValueError("Unexpected transaction identity or signing fields")
        _address(tx["to"])
        if not re.fullmatch(r"0x[0-9a-fA-F]*", tx.get("data", "")) or len(tx["data"]) % 2:
            raise ValueError("Malformed transaction calldata")
        if not re.fullmatch(r"0x[0-9a-fA-F]+", tx.get("value", "")):
            raise ValueError("Malformed transaction value")
    # Check the provider-declared destination. Router calldata is still unverified.
    summary = value.get("summary", {})
    if intent.action == "transfer":
        send = summary.get("send", {})
        if send.get("to", "").lower() != intent.destination:
            raise ValueError("Transfer recipient mismatch")
    if intent.action == "bridge":
        bridge = summary.get("bridge", {})
        if (
            bridge.get("receiver", "").lower() != intent.destination
            or bridge.get("toChain") != intent.destination_chain
        ):
            raise ValueError("Bridge destination mismatch")
    return prepared + timedelta(seconds=TTL_SECONDS)


class PreparationProvider(Protocol):
    def prepare(self, intent: PreparationIntent) -> dict[str, Any]: ...


class PreparationService:
    """One local operator store; reserve a request before calling its provider."""

    def __init__(
        self,
        provider: PreparationProvider | None = None,
        store_path: Path | None = None,
        *,
        clock: Callable[[], datetime] = utc_now,
    ):
        if provider is not None and store_path is None:
            raise ValueError("Enabled preparation requires a durable store")
        self.provider, self.path, self.clock = provider, store_path, clock

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        assert self.path is not None
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.is_symlink():
            raise ValueError("Preparation database cannot be a symlink")
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        except FileExistsError:
            if self.path.stat().st_mode & 0o077:
                raise ValueError("Preparation database requires mode 0600")
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS preparations "
            "(id TEXT PRIMARY KEY, intent_hash TEXT NOT NULL, "
            "state TEXT NOT NULL, created TEXT NOT NULL, expires TEXT, "
            "result TEXT, envelope TEXT)"
        )
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _result(status: str, **fields: Any) -> dict[str, Any]:
        return dict(
            provider="zerion",
            boundary="prepare",
            status=status,
            executed=False,
            execution_available=False,
            settlement="not_attempted",
            **fields,
        )

    def _stored(self, row: tuple[Any, ...]) -> dict[str, Any]:
        _, _, state, created, expires, result, _ = row
        if state == "prepared_unsigned" and datetime.fromisoformat(expires) <= self.clock():
            return self._result("expired", next_step="Prepare again with a new request ID.")
        if (
            state == "preparing"
            and (self.clock() - datetime.fromisoformat(created)).total_seconds() > 30
        ):
            return self._result(
                "preparation_unknown", next_step="Inspect the provider; no automatic retry."
            )
        return json.loads(result) if result else self._result(state)

    def get_status(self, request_id: str) -> dict[str, Any]:
        if not ID_RE.fullmatch(request_id):
            raise ValueError("Invalid request ID")
        if self.provider is None:
            return self._result("disabled")
        with self._connect() as db:
            row = db.execute("SELECT * FROM preparations WHERE id=?", (request_id,)).fetchone()
        return self._stored(row) if row else self._result("not_found")

    def prepare(self, request_id: str, intent: PreparationIntent) -> dict[str, Any]:
        if not ID_RE.fullmatch(request_id):
            raise ValueError("Invalid request ID")
        if self.provider is None:
            return self._result("disabled", next_step="Operator must configure Zerion preparation.")
        payload = json.dumps(intent.model_dump(), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode()).hexdigest()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM preparations WHERE id=?", (request_id,)).fetchone()
            if row:
                return self._stored(row) if row[1] == digest else self._result("intent_conflict")
            if db.execute("SELECT COUNT(*) FROM preparations").fetchone()[0] >= 5000:
                return self._result("store_full")
            db.execute(
                "INSERT INTO preparations VALUES (?, ?, ?, ?, NULL, NULL, NULL)",
                (request_id, digest, "preparing", self.clock().isoformat()),
            )
        try:
            envelope = self.provider.prepare(intent)
            raw = json.dumps(envelope, sort_keys=True, separators=(",", ":"), allow_nan=False)
            if len(raw.encode()) > 1_048_576:
                raise ValueError("Envelope too large")
            expiry = validate_envelope(envelope, intent, self.clock())
            result = self._result(
                "prepared_unsigned",
                request_id=request_id,
                intent=intent.model_dump(),
                expires_at=expiry.isoformat(),
                envelope_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                transaction_count=len(envelope["transactions"]),
                transaction_semantics_verified=False,
                next_step="Inspect the unsigned envelope locally. A separately "
                "authorized Zerion signing workflow is still required.",
            )
            state, expires = "prepared_unsigned", expiry.isoformat()
        except Exception:
            # Provider exception/output can contain credentials. Return only the fixed status.
            result = self._result(
                "preparation_failed",
                request_id=request_id,
                next_step="Inspect provider configuration; no automatic retry.",
            )
            state, expires, raw = "preparation_failed", None, None
        with self._connect() as db:
            db.execute(
                "UPDATE preparations SET state=?, expires=?, result=?, envelope=? WHERE id=?",
                (state, expires, json.dumps(result), raw, request_id),
            )
        return result
