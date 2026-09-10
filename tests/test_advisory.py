import math
from datetime import datetime, timezone

import pytest

from scout_portfolio_manager.advisory import (
    assess_yield,
    plan_zerion_action,
    portfolio_risk,
    validate_shock_pct,
)
from scout_portfolio_manager.contracts import Holding, PortfolioSnapshot, SourceMetadata


def snapshot(*holdings: Holding, observed_at: datetime | None = None) -> PortfolioSnapshot:
    timestamp = observed_at or datetime(2026, 9, 1, tzinfo=timezone.utc)
    return PortfolioSnapshot(
        wallet_address="0xabc",
        chain="ethereum",
        observed_at=timestamp,
        source=SourceMetadata(
            kind="fixture", locator="fixtures/portfolio.json", retrieved_at=timestamp
        ),
        holdings=list(holdings),
        transactions=[],
    )


def test_portfolio_risk_known_answer_and_provenance():
    result = portfolio_risk(
        snapshot(
            Holding(asset="ETH", quantity=1.0, value_usd=60.0),
            Holding(asset="USDC", quantity=40.0, value_usd=40.0),
        )
    )

    assert result["gross_observed_value_usd"] == 100.0
    assert result["top_exposure"] == {"asset": "ETH", "value_usd": 60.0, "weight": 0.6}
    assert result["hhi"] == pytest.approx(0.52)
    assert result["effective_position_count"] == pytest.approx(1 / 0.52)
    assert result["scenario"]["value_after_shock_usd"] == 70.0
    assert result["source"]["kind"] == "fixture"
    assert result["freshness"]["caller_must_validate_against_current_clock"] is True
    assert "correlations" in " ".join(result["limitations"]).lower()


def test_portfolio_risk_aggregates_duplicate_labels_and_ignores_zero_value_positions():
    result = portfolio_risk(
        snapshot(
            Holding(asset="ETH", quantity=1.0, value_usd=20.0),
            Holding(asset="ETH", quantity=2.0, value_usd=30.0),
            Holding(asset="ZERO", quantity=1.0, value_usd=0.0),
        )
    )

    assert result["positions"] == [{"asset": "ETH", "value_usd": 50.0, "weight": 1.0}]
    assert result["hhi"] == 1.0
    assert result["effective_position_count"] == 1.0


def test_portfolio_risk_empty_portfolio_has_no_division_artifacts():
    result = portfolio_risk(snapshot())
    assert result["positions"] == []
    assert result["top_exposure"] is None
    assert result["hhi"] == 0.0
    assert result["effective_position_count"] == 0.0


@pytest.mark.parametrize("shock", [math.nan, math.inf, -math.inf, True, -100.01, 100.01])
def test_portfolio_risk_rejects_invalid_shock(shock):
    with pytest.raises(ValueError):
        portfolio_risk(snapshot(), shock_pct=shock)


def test_validate_shock_can_run_before_snapshot_read():
    assert validate_shock_pct(-30) == -30.0


def test_portfolio_risk_rejects_overflowing_aggregate():
    with pytest.raises(ValueError, match="finite range"):
        portfolio_risk(
            snapshot(
                Holding(asset="ETH", quantity=1.0, value_usd=1e308),
                Holding(asset="ETH", quantity=1.0, value_usd=1e308),
            )
        )


def test_assess_yield_known_answer_and_components():
    result = assess_yield(1000, 5, fees_usd=10, days=365)
    assert result["base_yield_usd"] == 50.0
    assert result["reward_yield_usd"] == 0.0
    assert result["borrow_cost_usd"] == 0.0
    assert result["fees_usd"] == 10.0
    assert result["net_yield_usd"] == 40.0
    assert result["ending_value_usd"] == 1040.0
    assert result["method"] == "simple_non_compounding_scenario"
    assert result["rates_are_caller_supplied_assumptions"] is True


def test_assess_yield_keeps_rewards_borrow_and_fees_separate():
    result = assess_yield(2000, 4, reward_apr_pct=2, borrow_apr_pct=1, fees_usd=5, days=182.5)
    assert result["base_yield_usd"] == 40.0
    assert result["reward_yield_usd"] == 20.0
    assert result["borrow_cost_usd"] == 10.0
    assert result["net_yield_usd"] == 45.0


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"principal_usd": -1, "base_apr_pct": 1}, "principal_usd"),
        ({"principal_usd": 1, "base_apr_pct": math.nan}, "base_apr_pct"),
        ({"principal_usd": 1, "base_apr_pct": 1, "days": 0}, "days"),
        ({"principal_usd": 1, "base_apr_pct": 1, "fees_usd": -1}, "fees_usd"),
    ],
)
def test_assess_yield_rejects_invalid_inputs(kwargs, message):
    with pytest.raises(ValueError, match=message):
        assess_yield(**kwargs)


def test_assess_yield_rejects_overflowing_result():
    with pytest.raises(ValueError, match="finite range"):
        assess_yield(1e308, 10_000)


def test_plan_swap_is_zerion_only_and_never_executes():
    result = plan_zerion_action("swap", asset="ETH", amount=1, chain="ethereum", destination="USDC")
    assert result["provider"] == "zerion"
    assert result["execution_available"] is False
    assert result["action"] == "swap"
    assert result["missing_fields"] == []
    assert result["request"]["amount"] == 1.0
    assert "not integrated" in result["provider_context"].lower()
    assert "source_wallet" in result["required_for_future_execution"]


@pytest.mark.parametrize("action", ["swap", "bridge", "stake", "transfer", "payment"])
def test_portfolio_actions_report_missing_fields(action):
    result = plan_zerion_action(action)
    assert result["execution_available"] is False
    assert result["missing_fields"]
    assert result["alternate_provider"] is None


def test_data_access_describes_existing_configured_x402_route():
    result = plan_zerion_action("data_access")
    assert result["execution_available"] is False
    assert result["existing_route"]["kind"] == "x402_data_purchase"
    assert result["existing_route"]["operator_configuration_required"] is True
    assert result["existing_route"]["portfolio_action_execution"] is False


@pytest.mark.parametrize("action", ["buy", "sell", "", None])
def test_plan_action_rejects_unsupported_actions(action):
    with pytest.raises(ValueError, match="supported actions"):
        plan_zerion_action(action)  # type: ignore[arg-type]


@pytest.mark.parametrize("amount", [0, -1, math.nan, math.inf, True, "1"])
def test_plan_action_rejects_invalid_amount(amount):
    with pytest.raises(ValueError, match="amount"):
        plan_zerion_action("swap", asset="ETH", amount=amount, chain="ethereum")


def test_plan_action_rejects_long_or_secret_bearing_text():
    with pytest.raises(ValueError, match="200"):
        plan_zerion_action("swap", asset="x" * 201)
    with pytest.raises(ValueError, match="secret-bearing"):
        plan_zerion_action("transfer", destination="seed phrase: words")
