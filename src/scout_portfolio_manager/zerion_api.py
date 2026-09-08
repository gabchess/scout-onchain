"""Read-only adapter for Zerion's wallet positions and transactions endpoints.

``snapshot()`` builds a real per-asset portfolio from two calls: an unpaginated
call to ``/wallets/{addr}/positions/`` for holdings, and a cursor-paginated
walk of ``/wallets/{addr}/transactions/`` (via ``links.next``) for the ledger.
Zerion's own docs state ``/positions/`` takes no pagination parameters; only
``/transactions/`` paginates. NFT position list links are ``self``-only
(``ResponseManyLinks``) and are never followed here. Do not send
``filter[min_mined_at]`` / ``filter[max_mined_at]`` in this slice: those query
params are 13-character epoch-ms strings, while response ``mined_at`` is
ISO-8601. HTTP 429 has no ``Retry-After`` in the OpenAPI contract, but this
adapter parses one anyway when the response actually carries it (RFC 6585
defines the header for 429 regardless of what one API's docs mention); it is
``None`` only when the header is absent. Only positions 503 documents
``Retry-After`` in the contract itself. Never invent asset or ledger data: a
position missing a resolvable symbol, or a transaction with an unmapped
operation type or a malformed transfer, is skipped with a logged warning
rather than guessed at.
"""

from __future__ import annotations

import base64
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, Iterator, List, Literal, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from .contracts import Holding, PortfolioSnapshot, SourceMetadata, Transaction

logger = logging.getLogger(__name__)

EXPECTED_ZERION_API_HOST = "api.zerion.io"


class ZerionAPIError(RuntimeError):
    """Base class for safe, typed Zerion adapter failures."""

    def __init__(self, message: str, *, status: Optional[int] = None) -> None:
        self.status = status
        super().__init__(message)


class ZerionAPIAuthError(ZerionAPIError):
    """The API rejected the configured credential."""


class ZerionAPIRateLimitError(ZerionAPIError):
    """The API rate limit was reached (HTTP 429)."""

    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        retry_after_seconds: Optional[float] = None,
    ) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message, status=status)


class ZerionAPIPaymentError(ZerionAPIError):
    """x402 payment was rejected or failed to settle (HTTP 402)."""


class ZerionAPIServerError(ZerionAPIError):
    """The API reported a server-side failure (HTTP 5xx)."""

    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        retry_after_seconds: Optional[float] = None,
    ) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message, status=status)


class ZerionAPIPaginationError(ZerionAPIError):
    """Pagination could not be completed safely: bad cursor, loop, or page cap."""


class ZerionAPITransportError(ZerionAPIError):
    """The request could not be completed or decoded."""


class ZerionConfigError(ValueError):
    """The environment enables the Zerion source only partially or invalidly."""


@dataclass(frozen=True)
class ZerionAPIConfig:
    """Connection settings; the API key is excluded from representations.

    ``api_key`` is None only in x402 mode, where access is paid per request
    and no Authorization header is sent.
    """

    api_key: Optional[str] = field(repr=False)
    base_url: str = "https://api.zerion.io/v1"
    timeout_seconds: float = 10.0
    max_pages: int = 20
    """Caps the transaction walk at 20 pages (~2,000 transactions) by default.

    A snapshot also makes one positions request. In x402 mode, the default can
    therefore make up to 21 top-level API requests. Provider pricing can change.
    """

    def __post_init__(self) -> None:
        if self.api_key is not None and (
            not isinstance(self.api_key, str) or not self.api_key.strip()
        ):
            raise ValueError("api_key must be None (x402 mode) or a non-empty string")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        if (
            not isinstance(self.max_pages, int)
            or isinstance(self.max_pages, bool)
            or self.max_pages <= 0
        ):
            raise ValueError("max_pages must be a positive integer")
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https":
            raise ValueError("base_url must use https")
        if parsed.hostname != EXPECTED_ZERION_API_HOST:
            raise ValueError(f"base_url host must be {EXPECTED_ZERION_API_HOST}")


Transport = Callable[[Request, float], Mapping[str, Any]]


class ZerionAPIReader:
    """Observe one wallet's holdings and ledger through Zerion's read-only API."""

    def __init__(self, config: ZerionAPIConfig, *, transport: Optional[Transport] = None) -> None:
        self.config = config
        self._transport = transport or self._request

    # --- public reads --------------------------------------------------

    def snapshot(self, wallet_address: str, chain: str = "multi-chain") -> PortfolioSnapshot:
        """Build a real per-asset snapshot from positions and transactions."""
        self._validate_wallet_and_chain(wallet_address, chain)
        retrieved_at = datetime.now(timezone.utc)
        holdings = self.get_positions(wallet_address, chain)
        transactions = self.get_transactions(wallet_address, chain)
        locator = f"/wallets/{quote(wallet_address, safe='')}/positions/"
        return PortfolioSnapshot(
            wallet_address=wallet_address,
            chain=chain,
            observed_at=retrieved_at,
            source=SourceMetadata(kind="zerion_api", locator=locator, retrieved_at=retrieved_at),
            holdings=holdings,
            transactions=transactions,
        )

    def get_positions(self, wallet_address: str, chain: str = "multi-chain") -> List[Holding]:
        """Fetch every position for a wallet in one call; Zerion does not paginate this endpoint."""
        self._validate_wallet_and_chain(wallet_address, chain)
        payload = self._fetch(self._positions_url(wallet_address))
        items = payload.get("data")
        if not isinstance(items, list):
            raise ZerionAPIError("malformed Zerion positions response: data is not a list")
        holdings: List[Holding] = []
        for index, item in enumerate(items):
            holding = self._map_position(item, index)
            if holding is not None:
                holdings.append(holding)
        return holdings

    def get_transactions(
        self, wallet_address: str, chain: str = "multi-chain"
    ) -> List[Transaction]:
        """Fetch the wallet's transaction ledger, following links.next up to config.max_pages."""
        self._validate_wallet_and_chain(wallet_address, chain)
        transactions: List[Transaction] = []
        for item in self._paginate(self._transactions_url(wallet_address)):
            transactions.extend(self._map_transaction(item, wallet_address))
        return transactions

    # --- validation ------------------------------------------------------

    @staticmethod
    def _validate_wallet_and_chain(wallet_address: str, chain: str) -> None:
        if not isinstance(wallet_address, str) or not wallet_address.strip():
            raise ValueError("wallet_address must be non-empty")
        if not isinstance(chain, str) or not chain.strip():
            raise ValueError("chain must be non-empty")

    # --- pagination --------------------------------------------------------

    def _paginate(self, start_url: str) -> Iterator[Mapping[str, Any]]:
        """Yield every item across pages, following links.next.

        Raises ZerionAPIPaginationError on a malformed links object, a
        malformed or empty next cursor, a repeated cursor (loop guard), or
        exceeding config.max_pages while a next page is still indicated.
        """
        url: str = start_url
        seen: set[str] = set()
        for _ in range(self.config.max_pages):
            if url in seen:
                raise ZerionAPIPaginationError("Zerion API returned a repeated pagination cursor")
            seen.add(url)
            payload = self._fetch(url)
            items = payload.get("data")
            if not isinstance(items, list):
                raise ZerionAPIError("malformed Zerion transactions response: data is not a list")
            for item in items:
                yield item
            links = payload.get("links")
            if links is None:
                return
            if not isinstance(links, Mapping):
                raise ZerionAPIPaginationError("Zerion API returned a malformed links object")
            next_link = links.get("next")
            if next_link is None:
                return
            if not isinstance(next_link, str) or not next_link.strip():
                raise ZerionAPIPaginationError("Zerion API returned a malformed pagination cursor")
            self._validate_next_link_host(next_link)
            url = next_link
        raise ZerionAPIPaginationError(
            f"Zerion API pagination exceeded the {self.config.max_pages}-page bound"
        )

    @staticmethod
    def _validate_next_link_host(next_link: str) -> None:
        """Guard against following a pagination cursor off the expected Zerion host.

        ``_build_request`` attaches the Basic-auth API key header to whatever URL
        it is given, including a followed ``links.next`` cursor. Without this
        check, a malicious or corrupted next-link could redirect the request to
        an attacker-controlled host and exfiltrate the credential in the request
        header. Uses the same ``EXPECTED_ZERION_API_HOST`` that
        ``ZerionAPIConfig.__post_init__`` already validates ``base_url`` against.
        """
        parsed = urlparse(next_link)
        if parsed.scheme != "https" or parsed.hostname != EXPECTED_ZERION_API_HOST:
            raise ZerionAPIPaginationError(
                "Zerion API returned a pagination cursor pointing at an unexpected "
                f"host (expected https://{EXPECTED_ZERION_API_HOST}); refusing to follow it"
            )

    # --- mapping: positions ------------------------------------------------

    @staticmethod
    def _map_position(item: Any, index: int) -> Optional[Holding]:
        if not isinstance(item, Mapping):
            raise ZerionAPIError(
                f"malformed Zerion positions response: item {index} is not an object"
            )
        attributes = item.get("attributes")
        if not isinstance(attributes, Mapping):
            raise ZerionAPIError(
                f"malformed Zerion positions response: item {index} has no attributes"
            )
        fungible_info = attributes.get("fungible_info")
        symbol = fungible_info.get("symbol") if isinstance(fungible_info, Mapping) else None
        if not isinstance(symbol, str) or not symbol.strip():
            logger.warning("Zerion position %d skipped: missing fungible_info.symbol", index)
            return None
        quantity = ZerionAPIReader._numeric_amount(attributes.get("quantity"))
        value = ZerionAPIReader._number(attributes.get("value"))
        if quantity is None or value is None:
            logger.warning(
                "Zerion position %d (%s) skipped: missing or invalid quantity/value", index, symbol
            )
            return None
        return Holding(asset=symbol, quantity=quantity, value_usd=value)

    # --- mapping: transactions ----------------------------------------------

    #: operation_type -> {transfer direction -> Transaction.kind}
    _KIND_BY_OPERATION_AND_DIRECTION: Mapping[
        str, Mapping[str, Literal["buy", "sell", "transfer"]]
    ] = {
        "trade": {"in": "buy", "out": "sell"},
        "send": {"in": "transfer", "out": "transfer"},
        "receive": {"in": "transfer", "out": "transfer"},
        "deposit": {"in": "transfer", "out": "transfer"},
        "withdraw": {"in": "transfer", "out": "transfer"},
        "claim": {"in": "transfer", "out": "transfer"},
    }

    @staticmethod
    def _map_transaction(item: Any, wallet_address: str) -> List[Transaction]:
        if not isinstance(item, Mapping):
            raise ZerionAPIError("malformed Zerion transactions response: item is not an object")
        attributes = item.get("attributes")
        if not isinstance(attributes, Mapping):
            raise ZerionAPIError("malformed Zerion transactions response: item has no attributes")

        tx_id = item.get("id")
        if not isinstance(tx_id, str) or not tx_id.strip():
            tx_id = attributes.get("hash")
        if not isinstance(tx_id, str) or not tx_id.strip():
            raise ZerionAPIError("malformed Zerion transactions response: item has no id or hash")

        operation_type = attributes.get("operation_type")
        kind_by_direction = ZerionAPIReader._KIND_BY_OPERATION_AND_DIRECTION.get(
            operation_type if isinstance(operation_type, str) else ""
        )
        if kind_by_direction is None:
            logger.warning(
                "Zerion transaction %s skipped: unmapped operation_type %r", tx_id, operation_type
            )
            return []

        transfers = attributes.get("transfers")
        if not isinstance(transfers, list):
            logger.warning("Zerion transaction %s skipped: transfers is not a list", tx_id)
            return []

        occurred_at = ZerionAPIReader._parse_timestamp(
            attributes.get("mined_at"), datetime.now(timezone.utc)
        )

        # A transaction-level fee attaches to the first mapped row only, never
        # duplicated across rows produced by the same transaction.
        fee_usd = 0.0
        fee = attributes.get("fee")
        if isinstance(fee, Mapping):
            fee_value = ZerionAPIReader._number(fee.get("value"))
            if fee_value is not None:
                fee_usd = fee_value

        rows: List[Transaction] = []
        for index, transfer in enumerate(transfers):
            if not isinstance(transfer, Mapping):
                logger.warning(
                    "Zerion transaction %s transfer %d skipped: not an object", tx_id, index
                )
                continue
            direction = transfer.get("direction")
            kind = kind_by_direction.get(direction) if isinstance(direction, str) else None
            if kind is None:
                logger.warning(
                    "Zerion transaction %s transfer %d skipped: direction %r not mapped",
                    tx_id,
                    index,
                    direction,
                )
                continue
            fungible_info = transfer.get("fungible_info")
            symbol = fungible_info.get("symbol") if isinstance(fungible_info, Mapping) else None
            if not isinstance(symbol, str) or not symbol.strip():
                logger.warning(
                    "Zerion transaction %s transfer %d skipped: missing fungible_info.symbol",
                    tx_id,
                    index,
                )
                continue
            quantity = ZerionAPIReader._numeric_amount(transfer.get("quantity"))
            value = ZerionAPIReader._number(transfer.get("value"))
            if quantity is None or value is None:
                logger.warning(
                    "Zerion transaction %s transfer %d (%s) skipped: missing or invalid "
                    "quantity/value",
                    tx_id,
                    index,
                    symbol,
                )
                continue
            rows.append(
                Transaction(
                    id=f"{tx_id}-{index}",
                    kind=kind,
                    asset=symbol,
                    quantity=quantity,
                    value_usd=value,
                    fee_usd=fee_usd if not rows else 0.0,
                    occurred_at=occurred_at,
                    wallet_address=wallet_address,
                )
            )
        return rows

    # --- numeric and timestamp helpers --------------------------------------

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        value = float(value)
        return value if math.isfinite(value) and value >= 0 else None

    @staticmethod
    def _numeric_amount(value: Any) -> Optional[float]:
        """Accept either a bare number or a Zerion quantity object with a "float" key.

        Confirmed 2026-09-04: Zerion's documented positions/transactions field names
        (quantity, value, fungible_info) were confirmed by fetch, and ``quantity``
        is an object (as Zerion uses elsewhere in its API), not a bare float, for
        both endpoints. This still accepts both shapes rather than hard-failing on
        an unexpected one.
        """
        if isinstance(value, Mapping):
            value = value.get("float")
        return ZerionAPIReader._number(value)

    @staticmethod
    def _parse_timestamp(value: Any, fallback: datetime) -> datetime:
        if value is None:
            return fallback
        if not isinstance(value, str):
            raise ZerionAPIError("Zerion response contained an invalid timestamp")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ZerionAPIError("Zerion response contained an invalid timestamp") from None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    @staticmethod
    def _parse_retry_after(headers: Any) -> Optional[float]:
        """Read Retry-After as seconds (int) or an HTTP-date, or None if absent/unparseable."""
        if headers is None:
            return None
        try:
            value = headers.get("Retry-After")
        except AttributeError:
            return None
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            pass
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        delta = (parsed - datetime.now(timezone.utc)).total_seconds()
        return delta if delta >= 0 else 0.0

    # --- HTTP plumbing -------------------------------------------------------

    def _fetch(self, url: str) -> Mapping[str, Any]:
        try:
            return self._transport(self._build_request(url), self.config.timeout_seconds)
        except ZerionAPIError:
            raise
        except Exception as exc:
            # Injected transports are untrusted boundaries too; never expose
            # their exception text because it may contain credentials or URLs.
            raise ZerionAPITransportError("Zerion API transport failed") from exc

    def _headers(self) -> Dict[str, str]:
        if self.config.api_key is None:
            # x402 mode: no Authorization header. Access is settled per
            # request by the injected payment transport.
            return {"Accept": "application/json"}
        encoded = base64.b64encode((self.config.api_key + ":").encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {encoded}", "Accept": "application/json"}

    def _build_request(self, url: str) -> Request:
        return Request(url, headers=self._headers(), method="GET")

    def _positions_url(self, wallet_address: str) -> str:
        path = f"/wallets/{quote(wallet_address, safe='')}/positions/"
        query = (
            "currency=usd&filter%5Bpositions%5D=only_simple"
            "&filter%5Btrash%5D=only_non_trash"
        )
        return f"{self.config.base_url.rstrip('/')}{path}?{query}"

    def _transactions_url(self, wallet_address: str) -> str:
        path = f"/wallets/{quote(wallet_address, safe='')}/transactions/"
        query = (
            "currency=usd&page%5Bsize%5D=100"
            "&filter%5Boperation_types%5D=trade%2Csend%2Creceive"
            "&filter%5Btrash%5D=only_non_trash"
        )
        return f"{self.config.base_url.rstrip('/')}{path}?{query}"

    @staticmethod
    def _request(request: Request, timeout: float) -> Mapping[str, Any]:
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured API host
                payload = json.loads(response.read())
        except HTTPError as exc:
            retry_after = ZerionAPIReader._parse_retry_after(exc.headers)
            if exc.code in {401, 403}:
                raise ZerionAPIAuthError(
                    "Zerion API authorization failed", status=exc.code
                ) from None
            if exc.code == 404:
                # List endpoints return empty data, not 404. If Zerion ever
                # sends 404 on a list path, keep it as a generic API error
                # (status=404); the host maps that status to a "not_found"
                # observe-error kind without a dedicated exception type.
                raise ZerionAPIError(
                    "Zerion API returned HTTP 404", status=exc.code
                ) from None
            if exc.code == 429:
                # OpenAPI TooManyRequests does not document Retry-After, but
                # RFC 6585 defines the header for 429 regardless, so parse it
                # when the response actually sends one; None otherwise.
                raise ZerionAPIRateLimitError(
                    "Zerion API rate limit reached",
                    status=exc.code,
                    retry_after_seconds=retry_after,
                ) from None
            if 500 <= exc.code < 600:
                raise ZerionAPIServerError(
                    "Zerion API reported a server error",
                    status=exc.code,
                    retry_after_seconds=retry_after,
                ) from None
            raise ZerionAPIError(f"Zerion API returned HTTP {exc.code}", status=exc.code) from None
        except (
            URLError,
            TimeoutError,
            OSError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as exc:
            raise ZerionAPITransportError("Zerion API request or response failed") from exc
        if not isinstance(payload, Mapping):
            raise ZerionAPITransportError("Zerion API returned a non-object JSON response")
        return payload


class ZerionWalletReader:
    """One-wallet view of ZerionAPIReader matching the host's zero-argument reader protocol."""

    def __init__(
        self, reader: ZerionAPIReader, wallet_address: str, chain: str = "multi-chain"
    ) -> None:
        if not isinstance(wallet_address, str) or not wallet_address.strip():
            raise ValueError("wallet_address must be non-empty")
        self._reader = reader
        self.wallet_address = wallet_address
        self.chain = chain

    @property
    def authorization_mode(self) -> Literal["api_key", "x402"]:
        """Name the configured authorization boundary without exposing a secret."""
        return "x402" if self._reader.config.api_key is None else "api_key"

    def snapshot(self) -> PortfolioSnapshot:
        return self._reader.snapshot(self.wallet_address, self.chain)


# Environment variables that enable the read-only Zerion source. The key and the wallet
# must BOTH be present; a partial configuration is an error, never a fixture fallback.
API_KEY_ENV = "ZERION_API_KEY"
WALLET_ENV = "ZERION_WALLET_ADDRESS"
CHAIN_ENV = "ZERION_CHAIN"


def reader_from_env(
    environ: Mapping[str, str], *, transport: Optional[Transport] = None
) -> Optional[ZerionWalletReader]:
    """Build the Zerion source from the environment, or return None when it is not enabled.

    Authorization mode is exclusive: ``ZERION_X402_PRIVATE_KEY`` selects the
    pay-per-call x402 source (see ``x402_source``), otherwise
    ``ZERION_API_KEY`` selects the key-auth source. Returns None only when no
    variable is set. Raises ZerionConfigError on a partial configuration, so a
    half-configured host fails loudly instead of silently serving the
    fixture. The error message never contains the credential value.
    """
    from .x402_source import X402_KEY_ENV

    key = (environ.get(API_KEY_ENV) or "").strip()
    wallet = (environ.get(WALLET_ENV) or "").strip()
    x402_key = (environ.get(X402_KEY_ENV) or "").strip()
    if x402_key:
        if transport is not None:
            raise ZerionConfigError(
                "A custom transport cannot be injected in x402 mode; the x402 "
                "SDK owns the request transport."
            )
        from .x402_source import reader_from_env as x402_reader_from_env

        return x402_reader_from_env(environ)
    if not key and not wallet:
        return None
    if not key or not wallet:
        missing = WALLET_ENV if key else API_KEY_ENV
        raise ZerionConfigError(
            f"{API_KEY_ENV} and {WALLET_ENV} must both be set to enable the Zerion API "
            f"source; {missing} is missing. The fixture is not used as a fallback. "
            f"Alternatively, set {X402_KEY_ENV} and {WALLET_ENV} for pay-per-call "
            "x402 access."
        )
    chain = (environ.get(CHAIN_ENV) or "").strip() or "multi-chain"
    api_reader = ZerionAPIReader(ZerionAPIConfig(api_key=key), transport=transport)
    return ZerionWalletReader(api_reader, wallet, chain)
