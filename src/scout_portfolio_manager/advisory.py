"""Pure, bounded portfolio and DeFi advisory calculations."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .contracts import PortfolioSnapshot


def _finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be a finite number")
    return converted


def validate_shock_pct(value: object) -> float:
    """Validate a percentage shock before a caller obtains a portfolio snapshot."""
    shock = _finite_number("shock_pct", value)
    if not -100 <= shock <= 100:
        raise ValueError("shock_pct must be between -100 and 100")
    return shock


def _finite_result(name: str, value: float) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{name} is outside the supported finite range")
    return value


def portfolio_risk(snapshot: PortfolioSnapshot, shock_pct: float = -30.0) -> dict[str, Any]:
    """Describe concentration and a uniform price shock over observed gross holdings."""
    if not isinstance(snapshot, PortfolioSnapshot):
        raise ValueError("snapshot must be a PortfolioSnapshot")
    shock = validate_shock_pct(shock_pct)

    grouped: defaultdict[str, float] = defaultdict(float)
    for holding in snapshot.holdings:
        grouped[holding.asset] = _finite_result(
            "aggregated holding value", grouped[holding.asset] + holding.value_usd
        )

    total = _finite_result("gross observed value", sum(grouped.values()))
    positions: list[dict[str, Any]] = [
        {"asset": asset, "value_usd": value, "weight": value / total}
        for asset, value in grouped.items()
        if value > 0 and total > 0
    ]
    positions.sort(key=lambda item: (-item["value_usd"], item["asset"]))
    hhi = sum(position["weight"] ** 2 for position in positions)
    scenario_change = _finite_result("scenario change", total * shock / 100)
    scenario_value = _finite_result("scenario value", total + scenario_change)

    return {
        "analysis_scope": "gross_observed_holdings",
        "gross_observed_value_usd": total,
        "positions": positions,
        "top_exposure": positions[0] if positions else None,
        "hhi": hhi,
        "effective_position_count": 1 / hhi if hhi else 0.0,
        "scenario": {
            "shock_pct": shock,
            "assumption": "uniform shock applied equally to every observed holding",
            "change_usd": scenario_change,
            "value_after_shock_usd": scenario_value,
        },
        "source": {
            "kind": snapshot.source.kind,
            "locator": snapshot.source.locator,
            "retrieved_at": snapshot.source.retrieved_at.isoformat(),
        },
        "observed_at": snapshot.observed_at.isoformat(),
        "fixture": snapshot.source.kind == "fixture",
        "freshness": {
            "age_seconds": None,
            "caller_must_validate_against_current_clock": True,
            "note": "Timestamps are exposed without a claim that the data is current.",
        },
        "limitations": [
            "Gross observed holdings may not represent complete net worth or net exposure.",
            "Debt, protocol and chain look-through are unavailable.",
            "Correlations are unknown; the scenario assumes one uniform shock.",
            "Duplicate holdings are grouped by exact asset label; identity is not inferred.",
        ],
    }


def assess_yield(
    principal_usd: float,
    base_apr_pct: float,
    reward_apr_pct: float = 0.0,
    borrow_apr_pct: float = 0.0,
    fees_usd: float = 0.0,
    days: float = 365,
) -> dict[str, Any]:
    """Calculate a caller-supplied, simple non-compounding yield scenario."""
    principal = _finite_number("principal_usd", principal_usd)
    base_apr = _finite_number("base_apr_pct", base_apr_pct)
    reward_apr = _finite_number("reward_apr_pct", reward_apr_pct)
    borrow_apr = _finite_number("borrow_apr_pct", borrow_apr_pct)
    fees = _finite_number("fees_usd", fees_usd)
    horizon_days = _finite_number("days", days)

    if principal < 0:
        raise ValueError("principal_usd must be at least 0")
    if fees < 0:
        raise ValueError("fees_usd must be at least 0")
    for name, rate in (
        ("base_apr_pct", base_apr),
        ("reward_apr_pct", reward_apr),
        ("borrow_apr_pct", borrow_apr),
    ):
        if not 0 <= rate <= 10_000:
            raise ValueError(f"{name} must be between 0 and 10000")
    if not 0 < horizon_days <= 36_500:
        raise ValueError("days must be greater than 0 and no more than 36500")

    year_fraction = horizon_days / 365
    base_yield = _finite_result("base yield", principal * base_apr / 100 * year_fraction)
    reward_yield = _finite_result("reward yield", principal * reward_apr / 100 * year_fraction)
    borrow_cost = _finite_result("borrow cost", principal * borrow_apr / 100 * year_fraction)
    net_yield = _finite_result("net yield", base_yield + reward_yield - borrow_cost - fees)
    ending_value = _finite_result("ending value", principal + net_yield)

    return {
        "principal_usd": principal,
        "days": horizon_days,
        "method": "simple_non_compounding_scenario",
        "assumed_apr_pct": {
            "base": base_apr,
            "reward": reward_apr,
            "borrow": borrow_apr,
        },
        "base_yield_usd": base_yield,
        "reward_yield_usd": reward_yield,
        "borrow_cost_usd": borrow_cost,
        "fees_usd": fees,
        "net_yield_usd": net_yield,
        "ending_value_usd": ending_value,
        "rates_are_caller_supplied_assumptions": True,
        "source": "caller_input",
        "limitations": [
            "No live rates are fetched or ranked.",
            "Borrow APR is applied to the supplied principal, not an observed debt notional.",
            "The scenario excludes compounding, rate changes, price changes and liquidation.",
            "Smart-contract, lending, liquidity-pool and token-reward risks remain unmodeled.",
            "The result is a scenario, not a promise of realized return.",
        ],
    }


_SUPPORTED_ACTIONS = {"swap", "bridge", "stake", "transfer", "payment", "data_access"}
_REQUIRED_FIELDS = {
    "swap": ("asset", "amount", "chain", "destination"),
    "bridge": ("asset", "amount", "chain", "destination"),
    "stake": ("asset", "amount", "chain"),
    "transfer": ("asset", "amount", "chain", "destination"),
    "payment": ("asset", "amount", "chain", "destination"),
    "data_access": (),
}

_FUTURE_EXECUTION_FIELDS = {
    "swap": ("source_wallet", "target_asset", "slippage_limit", "quote_expiry", "approval"),
    "bridge": (
        "source_wallet",
        "destination_chain",
        "slippage_limit",
        "fee_limit",
        "quote_expiry",
        "approval",
    ),
    "stake": ("source_wallet", "staking_target", "fee_limit", "quote_expiry", "approval"),
    "transfer": ("source_wallet", "fee_limit", "approval"),
    "payment": ("source_wallet", "fee_limit", "approval"),
    "data_access": ("operator_authorization",),
}


def _bounded_text(name: str, value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > 200:
        raise ValueError(f"{name} must be no more than 200 characters")
    if any(marker in normalized.lower() for marker in ("private key", "seed phrase", "secret")):
        raise ValueError(f"{name} must not contain secret-bearing text")
    return normalized


def plan_zerion_action(
    action: str,
    asset: str | None = None,
    amount: float | None = None,
    chain: str | None = None,
    destination: str | None = None,
) -> dict[str, Any]:
    """Return a Zerion-only capability plan without execution, signing or network access."""
    if not isinstance(action, str) or action.strip().lower() not in _SUPPORTED_ACTIONS:
        supported = ", ".join(sorted(_SUPPORTED_ACTIONS))
        raise ValueError(f"action must be one of the supported actions: {supported}")
    normalized_action = action.strip().lower()
    normalized_amount = None
    if amount is not None:
        normalized_amount = _finite_number("amount", amount)
        if normalized_amount <= 0:
            raise ValueError("amount must be greater than 0")

    request = {
        "asset": _bounded_text("asset", asset),
        "amount": normalized_amount,
        "chain": _bounded_text("chain", chain),
        "destination": _bounded_text("destination", destination),
    }
    missing_fields = [
        field for field in _REQUIRED_FIELDS[normalized_action] if request[field] is None
    ]

    result: dict[str, Any] = {
        "action": normalized_action,
        "provider": "zerion",
        "alternate_provider": None,
        "request": request,
        "missing_fields": missing_fields,
        "required_for_future_execution": list(_FUTURE_EXECUTION_FIELDS[normalized_action]),
        "ready_for_execution": False,
        "execution_available": False,
        "reason": (
            "This action planner makes no network or signing calls, and Scout has no portfolio "
            "execution adapter."
        ),
        "provider_context": (
            "The official Zerion AI project has a trading CLI, but it is not integrated into Scout."
        ),
        "next_step": (
            "Supply the missing request fields and validate them in an authorized Zerion workflow."
            if missing_fields
            else "Review this request in an authorized Zerion workflow outside Scout."
        ),
    }
    if normalized_action == "stake":
        result["provider_context"] += (
            " Current Zerion staking support is unverified, so this is an intent record only."
        )
    if normalized_action == "data_access":
        result["existing_route"] = {
            "kind": "x402_data_purchase",
            "purpose": "authorized portfolio data access only",
            "operator_configuration_required": True,
            "spending_caps_apply": True,
            "portfolio_action_execution": False,
        }
        result["next_step"] = "Configure one documented authorization mode and retain its caps."
    return result
