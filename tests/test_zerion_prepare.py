"""Contract tests for unsigned preparation and durable replay protection."""

from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event

import pytest

from scout_portfolio_manager.zerion_prepare import PreparationIntent, PreparationService

WALLET = "0x" + "1" * 40
TOKEN = "0x" + "2" * 40
TARGET = "0x" + "3" * 40
NOW = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)


def intent(**changes):
    fields = dict(
        action="swap",
        chain="base",
        source_wallet=WALLET,
        asset=TOKEN,
        amount="100",
        target_asset=TARGET,
        slippage_bps=50,
    )
    return PreparationIntent(**(fields | changes))


def envelope():
    return {
        "kind": "zerion-prepared-group",
        "version": 1,
        "ecosystem": "evm",
        "chain": "base",
        "address": WALLET,
        "walletName": WALLET,
        "route": "web-app",
        "preparedAt": NOW.isoformat(),
        "summary": {"swap": {"sender": WALLET}},
        "outflows": [{"chain": "base", "tokenAddress": TOKEN, "amount": "100"}],
        "transactions": [
            {
                "evm": {
                    "from": WALLET,
                    "to": TARGET,
                    "chainId": "0x2105",
                    "value": "0x0",
                    "data": "0x1234",
                }
            }
        ],
    }


class Provider:
    def __init__(self, value=None):
        self.calls = 0
        self.value = value or envelope()

    def prepare(self, request):
        self.calls += 1
        return copy.deepcopy(self.value)


def test_disabled_does_not_create_store(tmp_path):
    service = PreparationService()
    assert service.prepare("one", intent())["status"] == "disabled"
    assert service.get_status("one")["status"] == "disabled"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": True},
        {"amount": 1},
        {"amount": "NaN"},
        {"amount": "-1"},
        {"amount": "0"},
        {"amount": "1e6"},
        {"amount": "1;ls"},
        {"asset": "USDC"},
        {"source_wallet": "--review"},
        {"slippage_bps": True},
        {"slippage_bps": 501},
        {"target_asset": None},
        {"action": "payment"},
        {"chain": "--help"},
        {"destination": WALLET},
        {"destination_chain": "arbitrum"},
    ],
)
def test_invalid_intent_rejected(changes):
    with pytest.raises(ValueError):
        intent(**changes)


def test_argv_has_explicit_review_prepare_and_exact_units():
    args = intent().cli_args()
    assert args[:5] == ["swap", "base", "100", TOKEN, TARGET]
    assert args[-6:] == ["--address", WALLET, "--slippage", "0.5", "--prepare", "--review"]
    assert intent(amount="100.00").model_dump() == intent().model_dump()


def test_send_and_bridge_arguments():
    send = intent(action="transfer", target_asset=None, destination=TARGET)
    assert send.cli_args()[:8] == [
        "send",
        TOKEN,
        "100",
        "--to",
        TARGET,
        "--chain",
        "base",
        "--address",
    ]
    bridge = intent(action="bridge", destination=TARGET, destination_chain="arbitrum")
    assert bridge.cli_args()[:6] == ["bridge", "base", TOKEN, "100", "arbitrum", TARGET]
    assert "--to-address" in bridge.cli_args()


def test_persisted_result_replays_across_restart(tmp_path):
    provider = Provider()
    path = tmp_path / "actions.db"
    service = PreparationService(provider, path, clock=lambda: NOW)
    first = service.prepare("same-id", intent())
    assert first["status"] == "prepared_unsigned"
    assert first["executed"] is False and first["settlement"] == "not_attempted"
    assert "transactions" not in first and "envelope" not in first
    second = PreparationService(provider, path, clock=lambda: NOW).prepare("same-id", intent())
    assert second["envelope_sha256"] == first["envelope_sha256"]
    assert provider.calls == 1
    assert service.prepare("same-id", intent(amount="101"))["status"] == "intent_conflict"
    assert provider.calls == 1


def test_expiry_never_reprepares_same_id(tmp_path):
    p = Provider()
    path = tmp_path / "actions.db"
    PreparationService(p, path, clock=lambda: NOW).prepare("id", intent())
    late = PreparationService(p, path, clock=lambda: NOW + timedelta(seconds=121))
    assert late.prepare("id", intent())["status"] == "expired"
    assert late.get_status("id")["status"] == "expired"
    assert p.calls == 1


@pytest.mark.parametrize(
    "mutation",
    [
        lambda e: e.update(address=TARGET),
        lambda e: e.update(chain="ethereum"),
        lambda e: e.update(route="local"),
        lambda e: e.update(version=2),
        lambda e: e.update(preparedAt=(NOW - timedelta(seconds=121)).isoformat()),
        lambda e: e.update(preparedAt=(NOW + timedelta(seconds=1)).isoformat()),
        lambda e: e["transactions"][0]["evm"].update(from_=TARGET, nonce="0x1"),
        lambda e: e["transactions"][0]["evm"].update(chainId="0x1"),
        lambda e: e["outflows"][0].update(amount="101"),
        lambda e: e["outflows"][0].update(tokenAddress=TARGET),
        lambda e: e.update(transactions=[]),
        lambda e: e.update(outflows=[]),
        lambda e: e.update(executed=True),
    ],
)
def test_provider_mismatch_never_returns_prepared(tmp_path, mutation):
    value = envelope()
    mutation(value)
    service = PreparationService(Provider(value), tmp_path / "db", clock=lambda: NOW)
    result = service.prepare("id", intent())
    assert result["status"] == "preparation_failed"
    assert result["executed"] is False
    assert "envelope_sha256" not in result


def test_timeout_is_durable_and_not_retried(tmp_path):
    class Fails(Provider):
        def prepare(self, request):
            self.calls += 1
            raise TimeoutError("secret must not be returned")

    provider = Fails()
    service = PreparationService(provider, tmp_path / "db", clock=lambda: NOW)
    result = service.prepare("id", intent())
    assert result["status"] == "preparation_failed"
    assert "secret" not in str(result)
    assert service.prepare("id", intent())["status"] == "preparation_failed"
    assert provider.calls == 1


def test_concurrent_duplicate_has_one_provider_call(tmp_path):
    entered, release = Event(), Event()

    class Slow(Provider):
        def prepare(self, request):
            entered.set()
            release.wait(5)
            return super().prepare(request)

    provider = Slow()
    service = PreparationService(provider, tmp_path / "db", clock=lambda: NOW)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(service.prepare, "id", intent())
        assert entered.wait(5)
        second = service.prepare("id", intent())
        assert second["status"] == "preparing"
        release.set()
        assert first.result()["status"] == "prepared_unsigned"
    assert provider.calls == 1


def test_unknown_and_invalid_request_ids(tmp_path):
    service = PreparationService(Provider(), tmp_path / "db", clock=lambda: NOW)
    assert service.get_status("absent")["status"] == "not_found"
    with pytest.raises(ValueError):
        service.prepare("../file", intent())
    assert not Path(tmp_path / "file").exists()
