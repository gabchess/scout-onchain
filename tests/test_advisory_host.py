import json
from pathlib import Path

import pytest

from scout_portfolio_manager.host import ReadOnlyHost, default_host
from scout_portfolio_manager.zerion_api import ZerionAPIRateLimitError

FIXTURE = Path(__file__).parents[1] / "fixtures" / "portfolio.json"


class NoRead:
    def snapshot(self):
        raise AssertionError("must not read or pay for data")


def test_nonportfolio_tools_never_read_wallet():
    host = ReadOnlyHost(NoRead())
    assert host.call_tool("search_defi_knowledge", {"query": "PDA"})["status"] == "ok"
    assert (
        host.call_tool(
            "assess_defi_yield",
            {
                "principal_usd": 1000,
                "base_apr_pct": 5,
                "fees_usd": 10,
            },
        )["net_yield_usd"]
        == 40
    )
    plan = host.call_tool("plan_zerion_action", {"action": "payment"})
    assert plan["provider"] == "zerion"
    assert plan["execution_available"] is False


@pytest.mark.parametrize("shock", [True, float("nan"), float("inf"), -101, 101, "30"])
def test_bad_risk_input_is_rejected_before_any_paid_read(shock):
    with pytest.raises(ValueError):
        ReadOnlyHost(NoRead()).get_portfolio_risk(shock)


def test_gross_risk_has_source_and_freshness_and_declared_scenario():
    result = default_host().get_portfolio_risk(-30)
    assert result["source"]["kind"] == "fixture"
    assert result["gross_observed_value_usd"] == 2250
    assert result["scenario"]["value_after_shock_usd"] == 1575
    assert result["freshness"]["state"] == "stale"
    assert result["execution_available"] is False
    json.dumps(result, allow_nan=False)


def test_source_failure_stays_a_source_failure():
    class FailingReader:
        def snapshot(self):
            raise ZerionAPIRateLimitError("rate limited")

    result = ReadOnlyHost(FailingReader()).get_portfolio_risk()
    assert result["status"] == "error"
    assert result["error"]["kind"] == "rate_limit"
    assert "gross_observed_value_usd" not in result


def test_risk_uses_one_read_and_exposes_existing_payment_budget():
    fixture = ReadOnlyHost(FIXTURE)

    class CountedReader:
        calls = 0
        spend_budget = {"remaining_usd": 0.5}

        def snapshot(self):
            self.calls += 1
            return fixture.reader.snapshot()

    reader = CountedReader()
    result = ReadOnlyHost(reader).get_portfolio_risk()
    assert reader.calls == 1
    assert result["x402_spend_budget"] == {"remaining_usd": 0.5}


@pytest.mark.parametrize("shock", [True, "30", "nan", -101])
def test_real_mcp_validation_cannot_coerce_bad_args_into_a_paid_read(shock):
    import asyncio

    from scout_portfolio_manager.mcp_server import create_server

    server = create_server(ReadOnlyHost(NoRead()))
    with pytest.raises(Exception) as error:
        asyncio.run(server.call_tool("get_portfolio_risk", {"shock_pct": shock}))
    assert "must not read" not in str(error.value)


def test_real_mcp_accepts_numeric_integer_shock():
    import asyncio

    from scout_portfolio_manager.mcp_server import create_server

    server = create_server(default_host())
    contents = asyncio.run(server.call_tool("get_portfolio_risk", {"shock_pct": -30}))
    text = contents[0][0].text if isinstance(contents, tuple) else contents[0].text
    assert json.loads(text)["scenario"]["value_after_shock_usd"] == 1575
