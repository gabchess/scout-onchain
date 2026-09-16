"""Arc unsigned preparation: intent rules, envelope binding, refusal status (ADR 0003)."""

from __future__ import annotations

import copy
import json
import sqlite3
import sys
from datetime import datetime, timezone
from decimal import Inexact
from pathlib import Path

import pytest
from tests.test_arc_read_path import arc_host

from scout_portfolio_manager.zerion_cli import ZerionCliProvider
from scout_portfolio_manager.zerion_prepare import (
    ARC_SAME_BALANCE,
    ARC_TRANSFERS_ONLY,
    ARC_USDC_NOTE,
    ARC_USDC_TOKEN,
    ChainNotSupported,
    PreparationIntent,
    PreparationService,
    scaled_units,
)

WALLET = "0x" + "1" * 40
DEST = "0x" + "2" * 40
EURC = "0x" + "4" * 40
ROUTER = "0x" + "5" * 40
NOW = datetime(2026, 9, 16, 12, tzinfo=timezone.utc)
ONE_USDC_18 = 10**18


def arc(**changes):
    fields = dict(
        action="transfer",
        chain="arc",
        source_wallet=WALLET,
        asset="native",
        amount="1",
        destination=DEST,
    )
    return PreparationIntent(**(fields | changes))


def tx(to=DEST, value=hex(ONE_USDC_18), data="0x", chain_id="0x13b2"):
    return {"evm": {"from": WALLET, "to": to, "chainId": chain_id, "value": value, "data": data}}


def arc_envelope(transactions=None, outflow=None, summary=None, amount="1", chain="arc") -> dict:
    return {
        "kind": "zerion-prepared-group",
        "version": 1,
        "ecosystem": "evm",
        "chain": chain,
        "address": WALLET,
        "route": "web-app",
        "preparedAt": NOW.isoformat(),
        "summary": summary if summary is not None else {"send": {"to": DEST}},
        "outflows": [
            outflow or {"chain": chain, "tokenAddress": None, "native": True, "amount": amount}
        ],
        "transactions": transactions if transactions is not None else [tx()],
    }


def transfer_calldata(recipient=DEST, units=10**6, extra=""):
    return "0xa9059cbb" + "0" * 24 + recipient[2:] + format(units, "064x") + extra


class Provider:
    def __init__(self, value=None, error=None):
        self.calls, self.value, self.error = 0, value, error

    def prepare(self, request):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return copy.deepcopy(self.value)


def prepare(tmp_path, request, value=None, error=None):
    provider = Provider(value, error)
    service = PreparationService(provider, tmp_path / "db", clock=lambda: NOW)
    return service.prepare("id", request), provider, service


# WP-1: intent rules


def test_arc_native_transfer_argv_uses_the_usdc_symbol():
    assert arc().cli_args()[:7] == ["send", "USDC", "1", "--to", DEST, "--chain", "arc"]


@pytest.mark.parametrize(
    "asset,target", [("native", ARC_USDC_TOKEN), (ARC_USDC_TOKEN, "native"), ("native", "native")]
)
def test_arc_usdc_swap_between_forms_is_refused(asset, target):
    with pytest.raises(ValueError, match="same balance"):
        arc(action="swap", destination=None, asset=asset, target_asset=target)


def test_base_native_swap_to_a_token_still_validates():
    request = arc(chain="base", action="swap", destination=None, target_asset=EURC)
    assert request.target_asset == EURC


@pytest.mark.parametrize(
    "changes",
    [
        dict(action="swap", destination=None, asset=ARC_USDC_TOKEN, target_asset=EURC),
        dict(
            action="bridge", asset=ARC_USDC_TOKEN, target_asset="native", destination_chain="base"
        ),
        dict(action="swap", destination=None, asset=EURC, target_asset=ARC_USDC_TOKEN),
        dict(
            chain="base",
            action="bridge",
            asset="native",
            target_asset=ARC_USDC_TOKEN,
            destination_chain="arc",
        ),
    ],
)
def test_arc_usdc_token_is_for_transfers_only(tmp_path, changes):
    with pytest.raises(ValueError, match="transfers only"):
        arc(**changes)
    host = arc_host(tmp_path)
    provider = Provider()
    host.preparation = PreparationService(provider, tmp_path / "db", clock=lambda: NOW)
    fields = (
        dict(
            request_id="arc-token",
            action="transfer",
            chain="arc",
            source_wallet=WALLET,
            asset="native",
            amount="1",
            destination=DEST,
        )
        | changes
    )
    with pytest.raises(ValueError, match="transfers only"):
        host.call_tool("prepare_zerion_transaction", fields)
    assert provider.calls == 0


def test_bridge_from_arc_to_an_address_that_matches_the_token_on_base_is_allowed():
    request = arc(action="bridge", target_asset=ARC_USDC_TOKEN, destination_chain="base")
    assert request.target_chain == "base"


def test_arc_usdc_token_transfer_validates():
    assert arc(asset=ARC_USDC_TOKEN).asset == ARC_USDC_TOKEN


@pytest.mark.parametrize("asset", ["native", ARC_USDC_TOKEN])
def test_arc_usdc_amount_has_at_most_six_decimal_places(asset):
    with pytest.raises(ValueError, match="6 decimal places"):
        arc(asset=asset, amount="1.0000001")
    assert arc(asset=asset, amount="1.000001").amount == "1.000001"


def test_other_arc_tokens_keep_the_eighteen_place_rule():
    assert arc(asset=EURC, amount="1.000000000000000001").amount == "1.000000000000000001"


def test_arc_testnet_is_rejected():
    with pytest.raises(ValueError, match="Unsupported preparation chain"):
        arc(chain="arc-testnet")


def test_messages_are_the_adr_text():
    assert ARC_SAME_BALANCE.startswith("On Arc, native USDC and the 0x3600 USDC token")
    assert ARC_TRANSFERS_ONLY.endswith("the 0x3600 token is accepted for transfers only.")


# WP-2: envelope binding


def test_arc_native_send_prepares(tmp_path):
    result, provider, _ = prepare(tmp_path, arc(), arc_envelope())
    assert result["status"] == "prepared_unsigned"
    assert result["executed"] is False and provider.calls == 1


@pytest.mark.parametrize(
    "transactions",
    [
        [tx(to=ROUTER)],
        [tx(data="0x1234")],
        [tx(value=hex(ONE_USDC_18 // 2)), tx(value=hex(ONE_USDC_18 // 2))],
        [tx(value=hex(10**6))],
        [tx(chain_id="0x4cef52")],
    ],
)
def test_arc_native_send_mismatch_fails_closed(tmp_path, transactions):
    result, _, _ = prepare(tmp_path, arc(), arc_envelope(transactions))
    assert result["status"] == "preparation_failed"


def test_arc_native_send_of_one_millionth_is_exactly_ten_to_the_twelve(tmp_path):
    envelope = arc_envelope([tx(value=hex(10**12))], amount="0.000001")
    result, _, _ = prepare(tmp_path, arc(amount="0.000001"), envelope)
    assert result["status"] == "prepared_unsigned"


def test_scaling_raises_on_an_inexact_result():
    assert scaled_units("0.000001", 18) == 10**12
    with pytest.raises(Inexact):
        scaled_units("0.0000001", 6)


def test_arc_native_swap_with_matching_value_prepares(tmp_path):
    request = arc(action="swap", destination=None, target_asset=EURC)
    envelope = arc_envelope(
        [tx(to=ROUTER, data="0x1234")],
        outflow={"chain": "arc", "tokenAddress": "0x" + "e" * 40, "amount": "1"},
        summary={"swap": {"sender": WALLET}},
    )
    result, _, _ = prepare(tmp_path, request, envelope)
    assert result["status"] == "prepared_unsigned"
    envelope["transactions"][0]["evm"]["value"] = hex(ONE_USDC_18 + 1)
    result, _, _ = prepare(tmp_path / "other", request, envelope)
    assert result["status"] == "preparation_failed"


def test_native_intent_with_erc20_fallback_outflow_fails_closed(tmp_path):
    envelope = arc_envelope(
        [tx(to=ARC_USDC_TOKEN, value="0x0", data=transfer_calldata())],
        outflow={"chain": "arc", "tokenAddress": ARC_USDC_TOKEN, "amount": "1"},
    )
    result, _, _ = prepare(tmp_path, arc(), envelope)
    assert result["status"] == "preparation_failed"


def token_envelope(**changes):
    fields = dict(to=ARC_USDC_TOKEN, value="0x0", data=transfer_calldata()) | changes
    return arc_envelope(
        [tx(**fields)], outflow={"chain": "arc", "tokenAddress": ARC_USDC_TOKEN, "amount": "1"}
    )


def test_arc_usdc_token_transfer_with_exact_calldata_prepares(tmp_path):
    result, _, _ = prepare(tmp_path, arc(asset=ARC_USDC_TOKEN), token_envelope())
    assert result["status"] == "prepared_unsigned"


@pytest.mark.parametrize(
    "changes",
    [
        dict(data=transfer_calldata(recipient=ROUTER)),
        dict(data=transfer_calldata(units=ONE_USDC_18)),
        dict(data=transfer_calldata(extra="00")),
        dict(value="0x1"),
        dict(to=ROUTER),
    ],
)
def test_arc_usdc_token_transfer_mismatch_fails_closed(tmp_path, changes):
    result, _, _ = prepare(tmp_path, arc(asset=ARC_USDC_TOKEN), token_envelope(**changes))
    assert result["status"] == "preparation_failed"


# WP-3: chain refusal status


@pytest.mark.parametrize(
    "code,reason",
    [
        ("unsupported_chain", "unknown_chain"),
        ("chain_capability_missing", "capability_missing"),
        ("chain_unsignable", "not_signable"),
    ],
)
def test_refusal_codes_map_to_terminal_status(tmp_path, code, reason):
    result, provider, service = prepare(tmp_path, arc(), error=ChainNotSupported(code))
    assert result["status"] == "chain_not_supported"
    assert result["reason"] == reason and result["retryable"] is False
    assert result["executed"] is False and provider.calls == 1
    assert service.prepare("id", arc()) == result
    assert service.get_status("id")["status"] == "chain_not_supported"
    assert provider.calls == 1


def test_unknown_refusal_code_cannot_be_constructed():
    with pytest.raises(ValueError):
        ChainNotSupported("missing_args")


def test_bridge_refusal_next_step_names_no_chain(tmp_path):
    request = arc(action="bridge", target_asset="native", destination_chain="base")
    result, _, _ = prepare(tmp_path, request, error=ChainNotSupported("chain_capability_missing"))
    text = result["next_step"].lower()
    assert "arc" not in text and "base" not in text


def fake_cli(root: Path, stderr: str = "", stdout: str = "", code: int = 1) -> Path:
    (root / "cli").mkdir(parents=True)
    (root / "package.json").write_text(json.dumps({"name": "zerion-cli", "version": "1.9.1"}))
    path = root / "cli/zerion.js"
    path.write_text(
        f"#!{sys.executable}\nimport sys\n"
        f"sys.stdout.write({stdout!r})\nsys.stdout.flush()\n"
        f"sys.stderr.write({stderr!r})\nsys.exit({code})\n"
    )
    path.chmod(0o700)
    return path


def cli_prepare(tmp_path, request, **cli):
    provider = ZerionCliProvider(
        fake_cli(tmp_path / "zerion", **cli), {"ZPM_ZERION_PREPARE_API_KEY": "k"}
    )
    service = PreparationService(provider, tmp_path / "db", clock=lambda: NOW)
    return service.prepare("id", request)


def refusal(code="chain_capability_missing", message="sk-secret leaked"):
    return json.dumps({"error": {"code": code, "message": message, "supportedChains": ["x"]}})


def test_base_cli_flag_refusal_is_chain_not_supported_and_leaks_nothing(tmp_path):
    request = arc(chain="base")
    result = cli_prepare(tmp_path, request, stderr=refusal())
    assert result["status"] == "chain_not_supported"
    assert result["reason"] == "capability_missing"
    assert "arc_usdc_note" not in result
    assert "sk-secret" not in json.dumps(result)
    with sqlite3.connect(tmp_path / "db") as db:
        assert "sk-secret" not in json.dumps(db.execute("SELECT * FROM preparations").fetchall())


@pytest.mark.parametrize(
    "cli",
    [
        dict(stderr="warning: slow\n" + refusal()),
        dict(stderr=json.dumps({"error": {"code": 7}})),
        dict(stderr=json.dumps([{"error": {"code": "unsupported_chain"}}])),
        dict(stderr=json.dumps({"error": {"code": "x", "message": "unsupported_chain"}})),
        dict(stderr=refusal(), code=2),
        dict(stderr=refusal(), stdout="{}"),
        dict(stderr=refusal(message="x" * 1_100_000)),
        dict(stderr=refusal(code="missing_args")),
        dict(stderr=b"\xff".decode("latin-1")),
    ],
)
def test_malformed_cli_refusals_stay_preparation_failed(tmp_path, cli):
    assert cli_prepare(tmp_path, arc(chain="base"), **cli)["status"] == "preparation_failed"


def test_refusal_is_not_swallowed_by_the_broad_handler(tmp_path):
    result, _, _ = prepare(tmp_path, arc(), error=ChainNotSupported("chain_unsignable"))
    assert result["status"] != "preparation_failed"


# WP-4: response note


def test_arc_usdc_note_on_every_terminal_status(tmp_path):
    ok, _, _ = prepare(tmp_path / "a", arc(), arc_envelope())
    refused, _, _ = prepare(tmp_path / "b", arc(), error=ChainNotSupported("unsupported_chain"))
    failed, _, _ = prepare(tmp_path / "c", arc(), error=TimeoutError())
    into_arc, _, _ = prepare(
        tmp_path / "d",
        arc(chain="base", action="bridge", target_asset="native", destination_chain="arc"),
        error=TimeoutError(),
    )
    for result in (ok, refused, failed, into_arc):
        assert result["arc_usdc_note"] == ARC_USDC_NOTE


def test_no_arc_usdc_note_on_base_or_other_arc_tokens(tmp_path):
    base, _, _ = prepare(tmp_path / "a", arc(chain="base"), error=TimeoutError())
    eurc, _, _ = prepare(tmp_path / "b", arc(asset=EURC), error=TimeoutError())
    assert "arc_usdc_note" not in base and "arc_usdc_note" not in eurc
