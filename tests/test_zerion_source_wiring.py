"""Env-gated wiring of the read-only Zerion source through the host and MCP entry point.

Rules under test: both env vars required, partial config fails loudly, no silent fixture
fallback, and the credential value never appears in errors or results.
"""

from pathlib import Path
from urllib.error import HTTPError

import pytest

from scout_portfolio_manager import mcp_server
from scout_portfolio_manager.host import ReadOnlyHost
from scout_portfolio_manager.portfolio import FixturePortfolioReader
from scout_portfolio_manager.zerion_api import (
    API_KEY_ENV,
    CHAIN_ENV,
    WALLET_ENV,
    ZerionAPIAuthError,
    ZerionAPIError,
    ZerionAPIRateLimitError,
    ZerionAPITransportError,
    ZerionConfigError,
    ZerionWalletReader,
    reader_from_env,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "portfolio.json"
CREDENTIAL = "opaque" + "-credential-value"
WALLET = "0xabc123"

# Positions/transactions-shaped responses mirroring the injected-transport pattern in
# tests/test_zerion_api.py: one ETH position, no matching buy transaction (so PnL has
# no acquisition basis).
POSITIONS_PAYLOAD = {
    "data": [
        {
            "attributes": {
                "quantity": 1.5,
                "value": 2017.48,
                "fungible_info": {"symbol": "ETH"},
            }
        }
    ]
}
TRANSACTIONS_PAYLOAD = {"data": []}


def positions_or_transactions_transport(request, timeout):
    if "/positions/" in request.full_url:
        return POSITIONS_PAYLOAD
    return TRANSACTIONS_PAYLOAD


def enabled_env(**extra):
    env = {API_KEY_ENV: CREDENTIAL, WALLET_ENV: WALLET}
    env.update(extra)
    return env


# --- reader_from_env gating -------------------------------------------------


def test_neither_variable_means_source_not_enabled():
    assert reader_from_env({}) is None
    assert reader_from_env({API_KEY_ENV: "  ", WALLET_ENV: ""}) is None


@pytest.mark.parametrize(
    "env, missing",
    [
        ({API_KEY_ENV: CREDENTIAL}, WALLET_ENV),
        ({WALLET_ENV: WALLET}, API_KEY_ENV),
        ({API_KEY_ENV: CREDENTIAL, WALLET_ENV: "   "}, WALLET_ENV),
    ],
)
def test_partial_configuration_fails_loudly_without_leaking_credential(env, missing):
    with pytest.raises(ZerionConfigError) as caught:
        reader_from_env(env)
    message = str(caught.value)
    assert missing in message
    assert "not used as a fallback" in message
    assert CREDENTIAL not in message


def test_both_variables_build_bound_wallet_reader_with_optional_chain():
    reader = reader_from_env(enabled_env())
    assert isinstance(reader, ZerionWalletReader)
    assert reader.wallet_address == WALLET
    assert reader.chain == "multi-chain"
    assert reader_from_env(enabled_env(**{CHAIN_ENV: "ethereum"})).chain == "ethereum"


def test_bound_reader_observes_configured_wallet_only():
    seen = []

    def transport(request, timeout):
        seen.append(request.full_url)
        return positions_or_transactions_transport(request, timeout)

    reader = reader_from_env(enabled_env(), transport=transport)
    snapshot = reader.snapshot()
    assert snapshot.wallet_address == WALLET
    assert snapshot.source.kind == "zerion_api"
    assert snapshot.holdings[0].asset == "ETH"
    assert snapshot.holdings[0].value_usd == pytest.approx(2017.48)
    assert snapshot.transactions == []
    assert seen == [
        f"https://api.zerion.io/v1/wallets/{WALLET}/positions/"
        "?currency=usd&filter%5Bpositions%5D=only_simple&filter%5Btrash%5D=only_non_trash",
        f"https://api.zerion.io/v1/wallets/{WALLET}/transactions/"
        "?currency=usd&page%5Bsize%5D=100&filter%5Boperation_types%5D=trade%2Csend%2Creceive"
        "&filter%5Btrash%5D=only_non_trash",
    ]
    assert CREDENTIAL not in repr(reader) and CREDENTIAL not in repr(reader._reader.config)


# --- host accepts a reader and never falls back ------------------------------


def test_host_reports_zerion_source_in_snapshot_and_pnl():
    host = ReadOnlyHost(
        reader_from_env(enabled_env(), transport=positions_or_transactions_transport)
    )
    snap = host.get_portfolio_snapshot()
    assert snap["status"] == "ok"
    assert snap["snapshot"]["source"]["kind"] == "zerion_api"
    assert snap["snapshot"]["wallet_address"] == WALLET
    assert snap["snapshot"]["holdings"][0]["asset"] == "ETH"
    pnl = host.get_pnl()
    assert pnl["status"] == "ok"
    assert pnl["results"] == []  # no buy transactions observed, so no acquisition basis
    assert pnl["unknown"] == ["missing acquisition basis for ETH"]


def test_host_returns_typed_error_and_no_fixture_data_when_api_rejects_credential(monkeypatch):
    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, 401, "denied " + CREDENTIAL, {}, None)

    monkeypatch.setattr("scout_portfolio_manager.zerion_api.urlopen", fake_urlopen)
    host = ReadOnlyHost(reader_from_env(enabled_env()))
    for result in (host.get_portfolio_snapshot(), host.get_pnl(asset="ETH")):
        assert result["status"] == "error"
        assert result["boundary"] == "observe"
        assert result["source"] == "zerion_api"
        assert result["fallback"] == "none"
        assert result["error"]["kind"] == "authorization"
        assert result["error"]["http_status"] == 401
        assert CREDENTIAL not in repr(result)
        assert "snapshot" not in result and "results" not in result


def test_host_error_kinds_are_typed():
    class Failing:
        def __init__(self, exc):
            self.exc = exc

        def snapshot(self):
            raise self.exc

    cases = [
        (ZerionAPIAuthError("auth", status=403), "authorization", 403, False),
        (ZerionAPIRateLimitError("slow down", status=429), "rate_limit", 429, True),
        (ZerionAPITransportError("transport"), "transport", None, True),
        (ZerionAPIError("malformed"), "api", None, False),
    ]
    for exc, kind, status, retryable in cases:
        result = ReadOnlyHost(Failing(exc)).get_portfolio_snapshot()
        assert result["error"] == {
            "kind": kind,
            "retryable": retryable,
            "message": str(exc),
            "http_status": status,
        }


def test_host_still_accepts_fixture_path_and_reader_objects():
    assert isinstance(ReadOnlyHost(FIXTURE).reader, FixturePortfolioReader)
    assert isinstance(ReadOnlyHost(str(FIXTURE)).reader, FixturePortfolioReader)
    fixture_reader = FixturePortfolioReader(FIXTURE)
    assert ReadOnlyHost(fixture_reader).reader is fixture_reader


def test_tool_manifest_unchanged_by_source():
    fixture_names = [t["name"] for t in ReadOnlyHost(FIXTURE).tool_manifest()]
    api_host = ReadOnlyHost(
        reader_from_env(enabled_env(), transport=positions_or_transactions_transport)
    )
    assert [t["name"] for t in api_host.tool_manifest()] == fixture_names
    assert not any("execute" in name for name in fixture_names)


# --- MCP entry point selection -----------------------------------------------


def test_build_host_defaults_to_fixture_when_source_not_enabled():
    host = mcp_server.build_host({})
    assert isinstance(host.reader, FixturePortfolioReader)
    host = mcp_server.build_host({"ZPM_FIXTURE_PATH": str(FIXTURE)})
    assert isinstance(host.reader, FixturePortfolioReader)
    assert host.reader.fixture_path == FIXTURE


def test_build_host_prefers_enabled_zerion_source_over_fixture_path():
    host = mcp_server.build_host(enabled_env(ZPM_FIXTURE_PATH=str(FIXTURE)))
    assert isinstance(host.reader, ZerionWalletReader)


def test_build_host_rejects_partial_configuration_instead_of_serving_fixture():
    with pytest.raises(ZerionConfigError):
        mcp_server.build_host({API_KEY_ENV: CREDENTIAL, "ZPM_FIXTURE_PATH": str(FIXTURE)})


def test_build_host_reads_process_environment_by_default(monkeypatch):
    monkeypatch.delenv("ZPM_FIXTURE_PATH", raising=False)
    monkeypatch.setenv(API_KEY_ENV, CREDENTIAL)
    monkeypatch.setenv(WALLET_ENV, WALLET)
    assert isinstance(mcp_server.build_host().reader, ZerionWalletReader)


def test_main_exits_cleanly_on_partial_configuration(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, CREDENTIAL)
    monkeypatch.delenv(WALLET_ENV, raising=False)
    with pytest.raises(SystemExit) as caught:
        mcp_server.main()
    assert WALLET_ENV in str(caught.value)
    assert CREDENTIAL not in str(caught.value)
