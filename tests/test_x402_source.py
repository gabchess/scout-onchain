"""Env-gated wiring of the optional x402 pay-per-call Zerion source.

Offline by construction: transport tests inject a fake session, while SDK
smoke tests create an ephemeral signer in memory. No network or money is used.

Rules under test: exclusive authorization modes, loud partial-config errors,
spend-cap validation, typed transport errors (including the non-retryable
402), and credentials that never appear in errors, reprs, or results.
"""

from pathlib import Path
from urllib.request import Request

import pytest

from scout_portfolio_manager.host import ReadOnlyHost
from scout_portfolio_manager.x402_source import (
    DEFAULT_MAX_PAYMENTS_PER_SESSION,
    DEFAULT_MAX_USD_PER_CALL,
    DEFAULT_MAX_USD_PER_SESSION,
    X402_KEY_ENV,
    X402_MAX_ENV,
    X402_SESSION_MAX_ENV,
    X402SpendBudget,
    parse_max_usd_per_call,
    parse_max_usd_per_session,
    x402_transport,
)
from scout_portfolio_manager.x402_source import (
    reader_from_env as x402_reader_from_env,
)
from scout_portfolio_manager.zerion_api import (
    API_KEY_ENV,
    WALLET_ENV,
    ZerionAPIAuthError,
    ZerionAPIBudgetError,
    ZerionAPIPaymentError,
    ZerionConfigError,
    reader_from_env,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "portfolio.json"
WALLET = "0xabc123"
# Deliberately not a real key shape: tests never build a real signer.
X402_KEY = "x402-payment-secret"

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


class FakeResponse:
    """Minimal stand-in for a requests.Response."""

    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = b"" if payload is None else _dumps(payload)


def _dumps(payload):
    import json

    return json.dumps(payload).encode("utf-8")


class FakeSession:
    """Injected session: records GET URLs, replays canned responses."""

    def __init__(self, status_code=200, payload=None, raise_exc=None, headers=None):
        self.status_code = status_code
        self.payload = payload
        self.raise_exc = raise_exc
        self.headers = headers
        self.gets = []
        self.request_headers = []

    def get(self, url, headers=None, timeout=None):
        self.gets.append(url)
        self.request_headers.append(headers or {})
        if self.raise_exc is not None:
            raise self.raise_exc
        payload = self.payload
        if payload is None:
            payload = POSITIONS_PAYLOAD if "/positions/" in url else TRANSACTIONS_PAYLOAD
        return FakeResponse(self.status_code, payload=payload, headers=self.headers)


def x402_env(**extra):
    env = {X402_KEY_ENV: X402_KEY, WALLET_ENV: WALLET}
    env.update(extra)
    return env


# --- spend cap validation -----------------------------------------------------


@pytest.mark.parametrize(
    "value",
    ["$0.05", "$1", "$0.01", "$10.50", "$0.1", "$0.00000000000000000001"],
)
def test_valid_money_strings_pass_through_unchanged(value):
    assert parse_max_usd_per_call(value) == value


@pytest.mark.parametrize(
    "value", ["", "garbage", "0.05", "$", "$-1", "$0", "USD 1", "$1$", "one dollar"]
)
def test_invalid_money_strings_are_loud_config_errors(value):
    with pytest.raises(ZerionConfigError) as caught:
        parse_max_usd_per_call(value)
    assert X402_MAX_ENV in str(caught.value)


def test_default_cap_is_five_cents():
    assert DEFAULT_MAX_USD_PER_CALL == "$0.05"


def test_default_session_budget_matches_one_nominal_max_page_snapshot():
    assert DEFAULT_MAX_PAYMENTS_PER_SESSION == 21
    assert DEFAULT_MAX_USD_PER_SESSION == "$1.05"


@pytest.mark.parametrize("value", ["$0.05", "$1.05", "$10"])
def test_valid_session_money_strings_pass_through(value):
    assert parse_max_usd_per_session(value) == value


def test_invalid_session_budget_is_a_loud_config_error():
    with pytest.raises(ZerionConfigError) as caught:
        parse_max_usd_per_session("unlimited")
    assert X402_SESSION_MAX_ENV in str(caught.value)


def test_budget_reserves_the_full_cap_and_stops_before_overspend():
    budget = X402SpendBudget.from_strings("$0.05", "$0.10")
    budget.reserve_payment()
    budget.reserve_payment()
    with pytest.raises(ZerionAPIBudgetError):
        budget.reserve_payment()
    assert budget.status() == {
        "max_usd_per_payment": "$0.05",
        "max_usd_per_session": "$0.10",
        "reserved_usd": "$0.10",
        "remaining_usd": "$0.00",
        "reserved_payments": 2,
        "accounting": "conservative_max_per_payment",
    }


# --- env gating ---------------------------------------------------------------


def test_x402_key_absent_means_source_not_enabled():
    assert x402_reader_from_env({}, session=FakeSession()) is None
    assert x402_reader_from_env({X402_KEY_ENV: "   "}, session=FakeSession()) is None


def test_top_level_reader_routes_to_x402_when_key_set(monkeypatch):
    from scout_portfolio_manager import x402_source

    monkeypatch.setattr(
        x402_source,
        "build_payment_session",
        lambda key, cap, spend_budget=None: FakeSession(),
    )
    reader = reader_from_env(x402_env())
    assert reader is not None
    assert reader.wallet_address == WALLET
    assert reader.chain == "multi-chain"


def test_missing_wallet_fails_loudly_without_leaking_credential():
    with pytest.raises(ZerionConfigError) as caught:
        x402_reader_from_env({X402_KEY_ENV: X402_KEY}, session=FakeSession())
    message = str(caught.value)
    assert WALLET_ENV in message
    assert "not used as a fallback" in message
    assert X402_KEY not in message


def test_both_authorization_modes_is_a_startup_error():
    with pytest.raises(ZerionConfigError) as caught:
        reader_from_env(x402_env(**{API_KEY_ENV: "a-key"}))
    message = str(caught.value)
    assert "not both" in message
    assert X402_KEY not in message and "a-key" not in message


def test_invalid_spend_cap_is_a_startup_error():
    with pytest.raises(ZerionConfigError):
        x402_reader_from_env(x402_env(**{X402_MAX_ENV: "free"}), session=FakeSession())


def test_custom_spend_cap_accepted():
    reader = x402_reader_from_env(x402_env(**{X402_MAX_ENV: "$0.10"}), session=FakeSession())
    assert reader is not None
    assert reader.spend_budget["max_usd_per_payment"] == "$0.10"
    assert reader.spend_budget["max_usd_per_session"] == "$2.10"


def test_custom_session_budget_accepted():
    reader = x402_reader_from_env(
        x402_env(**{X402_SESSION_MAX_ENV: "$0.25"}), session=FakeSession()
    )
    assert reader.spend_budget["max_usd_per_session"] == "$0.25"


def test_session_budget_smaller_than_payment_cap_is_rejected():
    with pytest.raises(ZerionConfigError, match=X402_SESSION_MAX_ENV):
        x402_reader_from_env(
            x402_env(
                **{
                    X402_MAX_ENV: "$0.10",
                    X402_SESSION_MAX_ENV: "$0.05",
                }
            ),
            session=FakeSession(),
        )


def test_transport_injection_refused_in_x402_mode():
    with pytest.raises(ZerionConfigError):
        reader_from_env(x402_env(), transport=lambda request, timeout: {})


# --- happy path through the host ------------------------------------------------


def test_bound_reader_observes_wallet_with_no_authorization_header():
    session = FakeSession()
    reader = x402_reader_from_env(x402_env(), session=session)
    snapshot = reader.snapshot()
    assert snapshot.wallet_address == WALLET
    assert snapshot.source.kind == "zerion_api"
    assert snapshot.holdings[0].asset == "ETH"
    assert snapshot.holdings[0].value_usd == pytest.approx(2017.48)
    assert snapshot.transactions == []
    assert reader.authorization_mode == "x402"
    # Exactly the two documented endpoints, nothing else.
    assert len(session.gets) == 2
    assert all("api.zerion.io/v1" in url for url in session.gets)
    assert all(headers.get("Accept") == "application/json" for headers in session.request_headers)
    # x402 mode sends no Basic-auth header; access is settled per request.
    assert reader._reader.config.api_key is None
    assert "Authorization" not in reader._reader._headers()
    assert X402_KEY not in repr(reader) and X402_KEY not in repr(reader._reader.config)


def test_host_reports_snapshot_from_x402_source():
    host = ReadOnlyHost(x402_reader_from_env(x402_env(), session=FakeSession()))
    snap = host.get_portfolio_snapshot()
    assert snap["status"] == "ok"
    assert snap["snapshot"]["source"]["kind"] == "zerion_api"
    assert snap["snapshot"]["wallet_address"] == WALLET
    assert snap["x402_spend_budget"]["remaining_usd"] == "$1.05"


# --- typed errors ----------------------------------------------------------------


def test_402_after_payment_attempt_is_typed_payment_error_not_retryable():
    session = FakeSession(status_code=402, payload={"errors": [{"detail": "rejected"}]})
    reader = x402_reader_from_env(x402_env(), session=session)
    with pytest.raises(ZerionAPIPaymentError) as caught:
        reader.snapshot()
    assert caught.value.status == 402


def test_host_maps_payment_error_to_payment_kind_non_retryable():
    session = FakeSession(status_code=402, payload={})
    host = ReadOnlyHost(x402_reader_from_env(x402_env(), session=session))
    result = host.get_portfolio_snapshot()
    assert result["status"] == "error"
    assert result["boundary"] == "observe"
    assert result["fallback"] == "none"
    assert result["error"]["kind"] == "payment"
    assert result["error"]["retryable"] is False
    assert result["error"]["http_status"] == 402
    assert X402_KEY not in repr(result)


def test_transport_exception_maps_to_transport_error():
    session = FakeSession(raise_exc=OSError("connection reset"))
    reader = x402_reader_from_env(x402_env(), session=session)
    from scout_portfolio_manager.zerion_api import ZerionAPITransportError

    with pytest.raises(ZerionAPITransportError) as caught:
        reader.snapshot()
    # The injected transport is an untrusted boundary: raw text never leaks.
    assert "connection reset" not in str(caught.value)


def test_wrapped_budget_stop_maps_to_typed_budget_error():
    pytest.importorskip("x402")
    from x402.http.clients.requests import PaymentError

    budget = X402SpendBudget.from_strings("$0.05", "$0.05")
    budget.reserve_payment()
    try:
        budget.reserve_payment()
    except ZerionAPIBudgetError as cause:
        try:
            raise PaymentError("wrapped SDK failure") from cause
        except PaymentError as wrapped:
            session = FakeSession(raise_exc=wrapped)
    transport = x402_transport(session)
    with pytest.raises(ZerionAPIBudgetError):
        transport(Request("https://api.zerion.io/v1/wallets/x/positions/"), 10.0)


def test_sdk_payment_error_maps_to_non_retryable_payment_without_leaking():
    pytest.importorskip("x402")
    from x402.http.clients.requests import PaymentError

    secret_detail = "payment-secret-detail"
    session = FakeSession(raise_exc=PaymentError(secret_detail))
    host = ReadOnlyHost(x402_reader_from_env(x402_env(), session=session))
    result = host.get_portfolio_snapshot()

    assert result["error"]["kind"] == "payment"
    assert result["error"]["retryable"] is False
    assert secret_detail not in repr(result)


def test_server_and_rate_limit_statuses_keep_their_kinds():
    from scout_portfolio_manager.zerion_api import (
        ZerionAPIRateLimitError,
        ZerionAPIServerError,
    )

    cases = [
        (429, ZerionAPIRateLimitError),
        (503, ZerionAPIServerError),
        (401, ZerionAPIAuthError),
    ]
    for status, expected in cases:
        session = FakeSession(status_code=status, payload={})
        reader = x402_reader_from_env(x402_env(), session=session)
        with pytest.raises(expected) as caught:
            reader.snapshot()
        assert caught.value.status == status


def test_missing_http_status_is_a_transport_error():
    class NoStatusSession:
        def get(self, url, headers=None, timeout=None):
            return object()

    from scout_portfolio_manager.zerion_api import ZerionAPITransportError

    transport = x402_transport(NoStatusSession())
    with pytest.raises(ZerionAPITransportError):
        transport(Request("https://api.zerion.io/v1/wallets/x/positions/"), 10.0)


def test_mcp_build_host_prefers_x402_source(monkeypatch):
    from scout_portfolio_manager import mcp_server, x402_source

    monkeypatch.setattr(
        x402_source,
        "build_payment_session",
        lambda key, cap, spend_budget=None: FakeSession(),
    )
    monkeypatch.setenv(X402_KEY_ENV, X402_KEY)
    monkeypatch.setenv(WALLET_ENV, WALLET)
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    monkeypatch.delenv("ZPM_FIXTURE_PATH", raising=False)
    host = mcp_server.build_host()
    # x402 source selected over the fixture; the SDK session builds lazily.
    assert host.reader.wallet_address == WALLET
    assert host.reader._reader.config.api_key is None


def test_fixture_remains_default_when_nothing_set(monkeypatch):
    from scout_portfolio_manager import mcp_server
    from scout_portfolio_manager.portfolio import FixturePortfolioReader

    monkeypatch.delenv(X402_KEY_ENV, raising=False)
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    monkeypatch.delenv(WALLET_ENV, raising=False)
    monkeypatch.delenv("ZPM_FIXTURE_PATH", raising=False)
    host = mcp_server.build_host()
    assert isinstance(host.reader, FixturePortfolioReader)


def test_transport_direct_status_mapping():
    transport = x402_transport(FakeSession(status_code=404, payload={}))
    from scout_portfolio_manager.zerion_api import ZerionAPIError

    with pytest.raises(ZerionAPIError) as caught:
        transport(Request("https://api.zerion.io/v1/wallets/x/positions/"), 10.0)
    assert caught.value.status == 404


# --- real SDK smoke (offline: key generated in-process, no network) ------------


def test_real_sdk_session_builds_with_spend_cap():
    """The production path builds a live x402 client; nothing leaves the process.

    The key is generated per-run and discarded, so no credential-shaped
    literal ever lands in the repo (the secret scanner would catch one).
    """
    pytest.importorskip("x402")
    from eth_account import Account

    from scout_portfolio_manager.x402_source import build_payment_session

    ephemeral = Account.create()
    budget = X402SpendBudget.from_strings("$0.05", "$0.05")
    session = build_payment_session(ephemeral.key.hex(), "$0.05", spend_budget=budget)
    assert session is not None
    # A real requests.Session with the x402 payment adapters mounted.
    assert hasattr(session, "get")
    client = session.get_adapter("https://")._client
    hook = client._before_payment_creation_hooks[-1]
    hook(None)
    with pytest.raises(ZerionAPIBudgetError):
        hook(None)


def test_real_sdk_rejects_invalid_private_key_without_leaking():
    pytest.importorskip("x402")
    from scout_portfolio_manager.x402_source import build_payment_session

    with pytest.raises(ZerionConfigError) as caught:
        build_payment_session("not-a-key", "$0.05")
    assert "not-a-key" not in str(caught.value)
    assert X402_KEY_ENV in str(caught.value)
