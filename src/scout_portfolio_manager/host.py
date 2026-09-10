"""Read-only host surface for agent runtimes.

Exposes observe, calculate, propose, and preview operations. No execute tool exists here.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from . import __version__
from .advisory import assess_yield, plan_zerion_action, portfolio_risk, validate_shock_pct
from .advisory_manifest import ADVISORY_TOOL_NAMES, advisory_manifest
from .alerts import AlertRule, AlertStore, evaluate_alert
from .analytics import (
    distance_from_range_pct,
    drawdown_from_cost_basis_pct,
    ema,
    range_30d,
    rsi,
    sma,
)
from .contracts import PortfolioSnapshot, Transaction
from .dca import DcaIntent, parse_dca_request
from .dca_windows import SIZING_FRACTION, classify_window
from .knowledge import search_knowledge
from .pnl import PnlResult, calculate_pnl
from .portfolio import FixturePortfolioReader, PortfolioReader
from .price_history import FixturePriceHistoryReader, PriceHistoryReader
from .safety import build_preview
from .zerion_api import (
    ZerionAPIAuthError,
    ZerionAPIBudgetError,
    ZerionAPIError,
    ZerionAPIPaginationError,
    ZerionAPIPaymentError,
    ZerionAPIRateLimitError,
    ZerionAPIServerError,
    ZerionAPITransportError,
)
from .zerion_prepare import PreparationIntent, PreparationService

logger = logging.getLogger(__name__)

# In-process counter of observe-boundary error kinds, keyed by the same
# "error.kind" string surfaced in _observe_error's response. Readable by a
# caller for basic aggregation; reset only by process restart.
_error_kind_counts: "Counter[str]" = Counter()


def error_kind_counts() -> Dict[str, int]:
    """Snapshot of in-process observe-error counts, keyed by error.kind."""
    return dict(_error_kind_counts)


TOOL_NAMES = (
    "get_portfolio_snapshot",
    "get_pnl",
    "parse_dca_request",
    "preview_dca",
    "analyze_asset",
    "dca_windows",
    "set_alert",
    "check_alerts",
) + ADVISORY_TOOL_NAMES

#: Default local path for AlertStore, relative to the process's current
#: working directory when no alerts_path is given. Gitignored: this is
#: per-operator local state, not a repo artifact.
DEFAULT_ALERTS_PATH = Path(".scout") / "alerts.json"

#: analyze_asset's freshness gate: how many days old the last observed price
#: point may be, relative to the snapshot's observed_at date, before the
#: response is flagged stale. Never used to suppress an indicator, only to
#: flag it; see analyze_asset's docstring.
DEFAULT_MAX_PRICE_AGE_DAYS = 2

#: analyze_asset and dca_windows never claim more than this. Nothing here is
#: backtested, so confidence is a fixed constant, not a computed one.
TA_CONFIDENCE = "low"
TA_DISCLOSURE = "Heuristic indicators, not backtested; treat as descriptive, not predictive."

#: Pinned verbatim, grepped by the release review pipeline: never reword.
NOT_FINANCIAL_ADVICE = "This is analysis, not financial advice."

# Deterministic fixture quote assumptions used only when the caller omits quote fields.
# Labeled as assumed so hosts never confuse them with observed market data.
DEFAULT_ETH_USD = 2250.0
DEFAULT_FEE_USD = 3.0
DEFAULT_SLIPPAGE_PCT = 0.5
DEFAULT_MAX_FEE_USD = 5.0
DEFAULT_QUOTE_TTL_SECONDS = 300


def _acquisition_basis_usd(transactions: Sequence[Transaction], asset: str) -> float:
    """Sum of buy transaction value + fee for one asset: the one basis calculation.

    Shared by get_pnl and analyze_asset so basis (a flow, summed from buy
    transactions) never drifts into two independently-computed numbers. Asset
    matching is case-sensitive against the transaction ledger, matching the
    existing PortfolioSnapshot/Transaction contract (fixture assets are
    already uppercase).
    """
    buys = [t for t in transactions if t.asset == asset and t.kind == "buy"]
    return sum(t.value_usd + t.fee_usd for t in buys)


class ReadOnlyHost:
    """Read-only adapter suitable for MCP or direct Python hosts.

    Accepts a fixture path (default) or any zero-argument PortfolioReader, such as the
    optional ZerionWalletReader. The host never switches source on its own: if the
    configured reader fails, callers get a typed error, not fixture data.
    """

    def __init__(
        self,
        source: Union[str, Path, PortfolioReader],
        *,
        price_history_path: Optional[Union[str, Path]] = None,
        alerts_path: Optional[Union[str, Path]] = None,
        preparation: PreparationService | None = None,
    ):
        self.preparation = preparation or PreparationService()
        self.reader: PortfolioReader = (
            FixturePortfolioReader(source) if isinstance(source, (str, Path)) else source
        )
        self._alert_store = AlertStore(
            alerts_path if alerts_path is not None else DEFAULT_ALERTS_PATH
        )
        # Price history is always fixture-backed, independent of the portfolio
        # source: no live price-history endpoint exists yet (see spec's
        # non-goals). Defaults to a sibling of the portfolio fixture path when
        # one is known, since fixtures/price_history.json ships next to
        # fixtures/portfolio.json; falls back to a bare relative path
        # otherwise (e.g. a live Zerion-backed portfolio reader with no
        # fixture path of its own), which analyze_asset's None-handling
        # already treats as "no price history observed".
        fixture_path_attr = getattr(self.reader, "fixture_path", None)
        if price_history_path is not None:
            resolved_price_history_path: Union[str, Path] = price_history_path
        elif isinstance(source, (str, Path)):
            resolved_price_history_path = Path(source).parent / "price_history.json"
        elif isinstance(fixture_path_attr, (str, Path)):
            resolved_price_history_path = Path(fixture_path_attr).parent / "price_history.json"
        else:
            resolved_price_history_path = Path("fixtures") / "price_history.json"
        self._price_history_reader: PriceHistoryReader = FixturePriceHistoryReader(
            resolved_price_history_path
        )

    def tool_manifest(self) -> List[Dict[str, Any]]:
        """MCP-shaped tool descriptors. No execute capability is advertised."""
        return [
            {
                "name": "get_portfolio_snapshot",
                "version": __version__,
                "description": (
                    "Observe the current portfolio snapshot from the configured read-only "
                    "source (fixture by default, or the Zerion API when enabled). "
                    "Read-only. Returns typed holdings and transactions."
                ),
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "get_pnl",
                "version": __version__,
                "description": (
                    "Calculate explainable USD PnL from the observed snapshot. "
                    "Optionally filter by asset symbol. Read-only."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "asset": {
                            "type": "string",
                            "description": "Optional asset filter, e.g. ETH",
                        }
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": "parse_dca_request",
                "version": __version__,
                "description": (
                    "Parse a user DCA request into explicit fields. "
                    "Missing fields produce clarification questions. Never infers wallets, "
                    "chains, schedules, source, or destination."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Natural-language DCA request from the user",
                        }
                    },
                    "required": ["text"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "preview_dca",
                "version": __version__,
                "description": (
                    "Parse a DCA request and, if complete, build a proposal with "
                    "approval_state=required. Optional quote fields come from the caller. "
                    "Scout does not fetch, execute, sign, or submit a swap."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Natural-language DCA request from the user",
                        },
                        "expected_output": {
                            "type": "number",
                            "description": (
                                "Optional quote output quantity. Assumed from fixture price "
                                "if omitted."
                            ),
                        },
                        "fees_usd": {
                            "type": "number",
                            "description": (
                                "Optional fee in USD. Defaults to a labeled fixture assumption."
                            ),
                        },
                        "slippage_pct": {
                            "type": "number",
                            "description": (
                                "Optional slippage percent. Defaults to a labeled fixture "
                                "assumption."
                            ),
                        },
                        "quote_expiry": {
                            "type": "string",
                            "description": (
                                "Optional ISO-8601 quote expiry. Defaults to now+5m UTC."
                            ),
                        },
                        "max_fee_usd": {
                            "type": "number",
                            "description": (
                                "Optional max fee. Defaults to a labeled fixture assumption."
                            ),
                        },
                    },
                    "required": ["text"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "analyze_asset",
                "version": __version__,
                "description": (
                    "Compute heuristic technical indicators (SMA, EMA, RSI, 30-day range, "
                    "drawdown from cost basis) for one asset from observed transactions plus "
                    "a synthetic price-history fixture. Read-only. Not backtested; descriptive, "
                    "not predictive."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "asset": {
                            "type": "string",
                            "description": "Asset symbol to analyze, e.g. ETH",
                        }
                    },
                    "required": ["asset"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "dca_windows",
                "version": __version__,
                "description": (
                    "Classify the current window as favorable, neutral, or unfavorable for a "
                    "DCA buy, sized by a risk-profile fraction. Reuses analyze_asset's RSI and "
                    "range-distance; never forecasts a future day. Not financial advice."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "asset": {
                            "type": "string",
                            "description": "Asset symbol to classify a DCA window for, e.g. ETH",
                        },
                        "risk_profile": {
                            "type": "string",
                            "enum": list(SIZING_FRACTION),
                            "description": "Sizing-fraction bucket. Defaults to 'balanced'.",
                        },
                        "amount_usd": {
                            "type": "number",
                            "description": (
                                "Optional DCA amount to size by the risk-profile fraction."
                            ),
                        },
                    },
                    "required": ["asset"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "set_alert",
                "version": __version__,
                "description": (
                    "Store a user-defined alert rule locally for later on-demand evaluation "
                    "by check_alerts. No daemon, no cron, no push: nothing fires by itself."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "asset": {"type": "string", "description": "Asset symbol, e.g. ETH"},
                        "kind": {
                            "type": "string",
                            "enum": ["price_pct_below_cost_basis", "rsi_below"],
                            "description": "Which observed value the rule watches.",
                        },
                        "threshold": {
                            "type": "number",
                            "description": "Threshold value the rule fires below.",
                        },
                    },
                    "required": ["asset", "kind", "threshold"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "check_alerts",
                "version": __version__,
                "description": (
                    "Evaluate stored alert rules on demand, once per call. Never runs in the "
                    "background. Stale price data is flagged, never used silently to decide a "
                    "fire/no-fire outcome."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "asset": {
                            "type": "string",
                            "description": "Optional asset filter, e.g. ETH",
                        }
                    },
                    "additionalProperties": False,
                },
            },
        ] + advisory_manifest(__version__)

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        arguments = arguments or {}
        if name in ADVISORY_TOOL_NAMES:
            methods: Dict[str, Callable[..., Dict[str, Any]]] = {
                "get_portfolio_risk": self.get_portfolio_risk,
                "assess_defi_yield": self.assess_defi_yield,
                "search_defi_knowledge": self.search_defi_knowledge,
                "plan_zerion_action": self.plan_zerion_action,
                "prepare_zerion_transaction": self.prepare_zerion_transaction,
                "get_zerion_preparation": self.get_zerion_preparation,
            }
            return methods[name](**arguments)
        if name == "get_portfolio_snapshot":
            return self.get_portfolio_snapshot()
        if name == "get_pnl":
            return self.get_pnl(asset=arguments.get("asset"))
        if name == "parse_dca_request":
            text = arguments.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("parse_dca_request requires non-empty text")
            return self.parse_dca_request(text)
        if name == "preview_dca":
            text = arguments.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("preview_dca requires non-empty text")
            return self.preview_dca(
                text,
                expected_output=arguments.get("expected_output"),
                fees_usd=arguments.get("fees_usd"),
                slippage_pct=arguments.get("slippage_pct"),
                quote_expiry=arguments.get("quote_expiry"),
                max_fee_usd=arguments.get("max_fee_usd"),
            )
        if name == "analyze_asset":
            asset = arguments.get("asset")
            if not isinstance(asset, str) or not asset.strip():
                raise ValueError("analyze_asset requires non-empty asset")
            return self.analyze_asset(asset)
        if name == "dca_windows":
            asset = arguments.get("asset")
            if not isinstance(asset, str) or not asset.strip():
                raise ValueError("dca_windows requires non-empty asset")
            return self.dca_windows(
                asset,
                risk_profile=arguments.get("risk_profile", "balanced"),
                amount_usd=arguments.get("amount_usd"),
            )
        if name == "set_alert":
            asset = arguments.get("asset")
            kind = arguments.get("kind")
            threshold = arguments.get("threshold")
            if not isinstance(asset, str) or not asset.strip():
                raise ValueError("set_alert requires non-empty asset")
            if not isinstance(kind, str) or not kind.strip():
                raise ValueError("set_alert requires non-empty kind")
            if not isinstance(threshold, (int, float)):
                raise ValueError("set_alert requires a numeric threshold")
            return self.set_alert(asset, kind, float(threshold))
        if name == "check_alerts":
            return self.check_alerts(asset=arguments.get("asset"))
        if name in {"execute", "execute_dca", "submit", "sign"}:
            raise PermissionError(
                f"{name} is not available on the read-only host; "
                "execution requires a separate authority decision"
            )
        raise ValueError(f"unknown tool: {name}")

    def get_portfolio_risk(self, shock_pct: float = -30.0) -> Dict[str, Any]:
        """Calculate concentration from one configured-source read; validate before spending."""
        shock = validate_shock_pct(shock_pct)
        try:
            snapshot = self.reader.snapshot()
        except ZerionAPIError as exc:
            return _observe_error(exc)
        result = portfolio_risk(snapshot, shock_pct=shock)
        observed = snapshot.observed_at
        if observed.tzinfo is not None:
            age = (datetime.now(timezone.utc) - observed).total_seconds()
            result["freshness"].update(
                age_seconds=age,
                max_age_seconds=900,
                state="future_timestamp" if age < 0 else "stale" if age > 900 else "recent",
            )
        else:
            result["freshness"].update(state="unknown_timezone", max_age_seconds=900)
        result.update(status="ok", boundary="calculate", execution_available=False)
        return self._with_source_budget(result)

    def assess_defi_yield(
        self,
        principal_usd: float,
        base_apr_pct: float,
        reward_apr_pct: float = 0.0,
        borrow_apr_pct: float = 0.0,
        fees_usd: float = 0.0,
        days: float = 365,
    ) -> Dict[str, Any]:
        """Calculate a scenario on caller assumptions without reading any wallet."""
        result = assess_yield(
            principal_usd, base_apr_pct, reward_apr_pct, borrow_apr_pct, fees_usd, days
        )
        result.update(status="ok", boundary="calculate", execution_available=False)
        return result

    def search_defi_knowledge(
        self,
        query: str,
        ecosystem: str | None = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        return search_knowledge(query, ecosystem=ecosystem, limit=limit)

    def plan_zerion_action(
        self,
        action: str,
        asset: str | None = None,
        amount: float | None = None,
        chain: str | None = None,
        destination: str | None = None,
    ) -> Dict[str, Any]:
        result = plan_zerion_action(action, asset, amount, chain, destination)
        result.update(status="proposal_only", boundary="propose")
        return result

    def prepare_zerion_transaction(
        self,
        request_id: str,
        action: str,
        chain: str,
        source_wallet: str,
        asset: str,
        amount: str,
        target_asset: str | None = None,
        destination: str | None = None,
        destination_chain: str | None = None,
        slippage_bps: int = 50,
    ) -> Dict[str, Any]:
        request = PreparationIntent.model_validate(
            dict(
                action=action,
                chain=chain,
                source_wallet=source_wallet,
                asset=asset,
                amount=amount,
                target_asset=target_asset,
                destination=destination,
                destination_chain=destination_chain,
                slippage_bps=slippage_bps,
            )
        )
        return self.preparation.prepare(request_id, request)

    def get_zerion_preparation(self, request_id: str) -> Dict[str, Any]:
        return self.preparation.get_status(request_id)

    def get_portfolio_snapshot(self) -> Dict[str, Any]:
        try:
            snapshot = self.reader.snapshot()
        except ZerionAPIError as exc:
            return _observe_error(exc)
        return self._with_source_budget(
            {
                "status": "ok",
                "boundary": "observe",
                "snapshot": snapshot.model_dump(mode="json"),
            }
        )

    def _with_source_budget(self, result: Dict[str, Any]) -> Dict[str, Any]:
        budget = getattr(self.reader, "spend_budget", None)
        if budget is not None:
            result["x402_spend_budget"] = dict(budget)
        return result

    @staticmethod
    def _pnl_from_snapshot(
        snapshot: PortfolioSnapshot, asset: Optional[str] = None
    ) -> Dict[str, Any]:
        target = asset.upper() if asset else None
        results: List[PnlResult] = []
        unknown: List[str] = []
        for holding in snapshot.holdings:
            if target and holding.asset.upper() != target:
                continue
            basis = _acquisition_basis_usd(snapshot.transactions, holding.asset)
            if not basis:
                unknown.append(f"missing acquisition basis for {holding.asset}")
                continue
            results.append(
                calculate_pnl(
                    holding=holding,
                    basis_usd=basis,
                    valuation_at=snapshot.observed_at,
                    transactions=snapshot.transactions,
                )
            )
        if target and not results and not unknown:
            unknown.append(f"no holding observed for {target}")
        return {
            "status": "ok",
            "boundary": "calculate",
            "results": [r.model_dump(mode="json") for r in results],
            "unknown": unknown,
        }

    def get_pnl(self, asset: Optional[str] = None) -> Dict[str, Any]:
        try:
            snapshot = self.reader.snapshot()
        except ZerionAPIError as exc:
            return _observe_error(exc)
        return self._with_source_budget(self._pnl_from_snapshot(snapshot, asset))

    def analyze_asset(self, asset: str) -> Dict[str, Any]:
        """Heuristic TA indicators for one asset. Read-only, never raises on a data gap.

        Reuses get_pnl's acquisition-basis calculation for drawdown (one basis
        sum, not two independently-drifting ones). Price-derived indicators
        come from the fixture-backed price-history reader configured on this
        host, independent of whichever portfolio source is configured.
        Confidence is always "low": nothing here is backtested.
        """
        try:
            snapshot = self.reader.snapshot()
        except ZerionAPIError as exc:
            return _observe_error(exc)

        return self._with_source_budget(self._analysis_from_snapshot(snapshot, asset))

    def _analysis_from_snapshot(self, snapshot: PortfolioSnapshot, asset: str) -> Dict[str, Any]:
        """Calculate one asset analysis without observing the wallet again."""

        asset = asset.upper()
        unknown: List[str] = []
        indicators: Dict[str, Any] = {}
        freshness: Optional[Dict[str, Any]] = None

        history = self._price_history_reader.series(asset)
        if history is None:
            unknown.append(f"no price history observed for {asset}")
        else:
            closes = [p.close_usd for p in history.points]
            last_price_date = history.points[-1].date
            stale = (snapshot.observed_at.date() - last_price_date).days > (
                DEFAULT_MAX_PRICE_AGE_DAYS
            )
            freshness = {
                "stale": stale,
                "max_age_days": DEFAULT_MAX_PRICE_AGE_DAYS,
                "last_price_date": last_price_date.isoformat(),
            }
            sma_20 = sma(closes, 20)
            if sma_20 is not None:
                indicators["sma_20"] = round(sma_20, 4)
            ema_12 = ema(closes, 12)
            if ema_12 is not None:
                indicators["ema_12"] = round(ema_12, 4)
            rsi_14 = rsi(closes, 14)
            if rsi_14 is not None:
                indicators["rsi_14"] = round(rsi_14, 4)
            range30 = range_30d(closes)
            if range30 is not None:
                indicators["range_30d"] = range30
                indicators["distance_from_range_pct"] = {
                    key: round(value, 4)
                    for key, value in distance_from_range_pct(
                        closes[-1], range30["low"], range30["high"]
                    ).items()
                }

        basis = _acquisition_basis_usd(snapshot.transactions, asset)
        holding = next((h for h in snapshot.holdings if h.asset.upper() == asset), None)
        if basis and holding is not None:
            indicators["drawdown_from_cost_basis_pct"] = round(
                drawdown_from_cost_basis_pct(holding.value_usd, basis), 4
            )
        else:
            unknown.append(f"missing acquisition basis for {asset}")

        result: Dict[str, Any] = {
            "status": "ok",
            "boundary": "calculate",
            "asset": asset,
            "as_of": snapshot.observed_at.isoformat().replace("+00:00", "Z"),
            "indicators": indicators,
            "unknown": unknown,
            "confidence": TA_CONFIDENCE,
            "disclosure": TA_DISCLOSURE,
        }
        if freshness is not None:
            result["freshness"] = freshness
        if history is not None:
            result["price_history_source"] = history.source.model_dump(mode="json")
        return result

    def dca_windows(
        self,
        asset: str,
        risk_profile: str = "balanced",
        amount_usd: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Classify the current window for a DCA buy. Proposes, never executes.

        Reuses analyze_asset's rsi_14 and distance_from_range_pct rather than
        recomputing them: one RSI/range implementation, one place. Window is
        always "current"; this never forecasts a future day. Also propagates
        analyze_asset's freshness so a stale price series is never silently
        used to produce a favorable/unfavorable classification.
        """
        if risk_profile not in SIZING_FRACTION:
            raise ValueError(f"unknown risk_profile: {risk_profile!r}")
        try:
            snapshot = self.reader.snapshot()
        except ZerionAPIError as exc:
            return _observe_error(exc)
        analysis = self._analysis_from_snapshot(snapshot, asset)
        return self._with_source_budget(
            self._window_from_analysis(
                analysis,
                risk_profile=risk_profile,
                amount_usd=amount_usd,
            )
        )

    @staticmethod
    def _window_from_analysis(
        analysis: Dict[str, Any],
        *,
        risk_profile: str,
        amount_usd: Optional[float],
    ) -> Dict[str, Any]:
        """Build one DCA window from an already-computed analysis."""
        if risk_profile not in SIZING_FRACTION:
            raise ValueError(f"unknown risk_profile: {risk_profile!r}")

        indicators = analysis["indicators"]
        classification = classify_window(
            rsi_14=indicators.get("rsi_14"),
            distance_from_range_pct=indicators.get("distance_from_range_pct"),
            risk_profile=risk_profile,  # type: ignore[arg-type]
            amount_usd=amount_usd,
        )
        result: Dict[str, Any] = {
            "status": "ok",
            "boundary": "propose",
            "asset": analysis["asset"],
            "window": "current",
            "label": classification["label"],
            "risk_profile": classification["risk_profile"],
            "sizing_fraction": classification["sizing_fraction"],
            "rationale": classification["rationale"],
            "sensitivity_note": classification["sensitivity_note"],
            "confidence": TA_CONFIDENCE,
            "disclosure": TA_DISCLOSURE,
            "not_financial_advice": NOT_FINANCIAL_ADVICE,
        }
        if "suggested_amount_usd" in classification:
            result["suggested_amount_usd"] = classification["suggested_amount_usd"]
        if analysis.get("freshness") is not None:
            result["freshness"] = analysis["freshness"]
        if analysis.get("price_history_source") is not None:
            result["price_history_source"] = analysis["price_history_source"]
        return result

    def set_alert(self, asset: str, kind: str, threshold: float) -> Dict[str, Any]:
        """Store a user-defined alert rule locally. No daemon, no cron, no push."""
        rule = self._alert_store.add(asset=asset, kind=kind, threshold=threshold)
        return {
            "status": "ok",
            "boundary": "propose",
            "rule": rule.model_dump(mode="json"),
            "rule_count": len(self._alert_store.list()),
        }

    def check_alerts(self, asset: Optional[str] = None) -> Dict[str, Any]:
        """Evaluate stored alert rules on demand. Never runs in the background.

        One wallet snapshot is shared across every matched rule. An asset with
        no observed price history or basis lands in "unknown", never silently
        dropped.
        """
        target = asset.upper() if asset else None
        rules = self._alert_store.list(asset=target)
        if not rules:
            return self._with_source_budget(self._empty_alert_result())
        try:
            snapshot = self.reader.snapshot()
        except ZerionAPIError as exc:
            return _observe_error(exc)
        return self._with_source_budget(self._alerts_from_snapshot(snapshot, rules))

    @staticmethod
    def _empty_alert_result() -> Dict[str, Any]:
        return {
            "status": "ok",
            "boundary": "calculate",
            "fired": [],
            "not_fired": [],
            "unknown": [],
            "not_financial_advice": NOT_FINANCIAL_ADVICE,
        }

    def _alerts_from_snapshot(
        self,
        snapshot: PortfolioSnapshot,
        rules: Sequence[AlertRule],
        *,
        analyses: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Evaluate alert rules from one shared wallet observation."""
        if not rules:
            return self._empty_alert_result()
        fired: List[Dict[str, Any]] = []
        not_fired: List[Dict[str, Any]] = []
        unknown: List[str] = []

        distinct_assets = sorted({rule.asset for rule in rules})
        analysis_cache: Dict[str, Dict[str, Any]] = dict(analyses or {})
        pnls: Dict[str, Dict[str, Any]] = {}
        for a in distinct_assets:
            if a not in analysis_cache:
                analysis_cache[a] = self._analysis_from_snapshot(snapshot, a)
            if any(r.asset == a and r.kind == "price_pct_below_cost_basis" for r in rules):
                pnls[a] = self._pnl_from_snapshot(snapshot, asset=a)

        for rule in rules:
            analysis = analysis_cache[rule.asset]
            if analysis["status"] != "ok":
                unknown.append(f"could not observe {rule.asset} for rule {rule.id}")
                continue
            evaluated = evaluate_alert(rule, analysis=analysis, pnl=pnls.get(rule.asset))
            if evaluated["observed_value"] is None:
                unknown.append(f"no observed value for rule {rule.id} on {rule.asset}")
                continue
            (fired if evaluated["fired"] else not_fired).append(evaluated)

        return {
            "status": "ok",
            "boundary": "calculate",
            "fired": fired,
            "not_fired": not_fired,
            "unknown": unknown,
            "not_financial_advice": NOT_FINANCIAL_ADVICE,
        }

    def build_report_data(self) -> Dict[str, Any]:
        """Observe once, then derive every watch-report panel from that snapshot."""
        try:
            snapshot = self.reader.snapshot()
        except ZerionAPIError as exc:
            return _observe_error(exc)

        snapshot_json = snapshot.model_dump(mode="json")
        pnl = self._pnl_from_snapshot(snapshot)
        analyses: Dict[str, Dict[str, Any]] = {}
        windows: Dict[str, Dict[str, Any]] = {}
        for holding in snapshot.holdings:
            asset = holding.asset
            analysis = self._analysis_from_snapshot(snapshot, asset)
            analyses[asset] = analysis
            windows[asset] = self._window_from_analysis(
                analysis,
                risk_profile="balanced",
                amount_usd=None,
            )
        alerts = self._alerts_from_snapshot(
            snapshot,
            self._alert_store.list(),
            analyses=analyses,
        )
        return self._with_source_budget(
            {
                "status": "ok",
                "boundary": "report",
                "snapshot": snapshot_json,
                "pnl": pnl,
                "analyses": analyses,
                "windows": windows,
                "alerts": alerts,
            }
        )

    def parse_dca_request(self, text: str) -> Dict[str, Any]:
        parsed = parse_dca_request(text)
        return {
            "status": parsed.status,
            "boundary": "propose",
            "intent": parsed.intent.model_dump(mode="json"),
            "missing": parsed.missing,
            "question": parsed.question,
        }

    def preview_dca(
        self,
        text: str,
        *,
        expected_output: Optional[float] = None,
        fees_usd: Optional[float] = None,
        slippage_pct: Optional[float] = None,
        quote_expiry: Optional[Union[str, datetime]] = None,
        max_fee_usd: Optional[float] = None,
    ) -> Dict[str, Any]:
        parsed = parse_dca_request(text)
        if parsed.status != "ready":
            return {
                "status": "needs_clarification",
                "boundary": "propose",
                "intent": parsed.intent.model_dump(mode="json"),
                "missing": parsed.missing,
                "question": parsed.question,
                "preview": None,
            }

        assumed: List[str] = []
        intent = parsed.intent
        assert intent.amount_usd is not None  # ready status guarantees this

        if expected_output is None:
            if intent.asset == "ETH":
                expected_output = round(intent.amount_usd / DEFAULT_ETH_USD, 8)
                assumed.append(
                    f"expected_output derived from DEFAULT_ETH_USD (${DEFAULT_ETH_USD}), a "
                    "fixture-only placeholder price, never a live quote, regardless of the "
                    "configured portfolio source"
                )
            else:
                expected_output = 0.0
                assumed.append(
                    f"expected_output defaulted to 0.0: no fixture or live quote price is "
                    f"configured for {intent.asset}"
                )
        if fees_usd is None:
            fees_usd = DEFAULT_FEE_USD
            assumed.append(f"fees_usd assumed {DEFAULT_FEE_USD}")
        if slippage_pct is None:
            slippage_pct = DEFAULT_SLIPPAGE_PCT
            assumed.append(f"slippage_pct assumed {DEFAULT_SLIPPAGE_PCT}")
        if max_fee_usd is None:
            max_fee_usd = DEFAULT_MAX_FEE_USD
            assumed.append(f"max_fee_usd assumed {DEFAULT_MAX_FEE_USD}")
        if quote_expiry is None:
            expiry = datetime.now(timezone.utc) + timedelta(seconds=DEFAULT_QUOTE_TTL_SECONDS)
            assumed.append(f"quote_expiry assumed now+{DEFAULT_QUOTE_TTL_SECONDS}s")
        elif isinstance(quote_expiry, str):
            expiry = datetime.fromisoformat(quote_expiry.replace("Z", "+00:00"))
        else:
            expiry = quote_expiry

        preview = build_preview(
            intent=DcaIntent.model_validate(intent.model_dump()),
            expected_output=float(expected_output),
            fees_usd=float(fees_usd),
            slippage_pct=float(slippage_pct),
            quote_expiry=expiry,
            max_fee_usd=float(max_fee_usd) if max_fee_usd is not None else None,
        )
        return {
            "status": "preview_ready",
            "boundary": "preview",
            "preview_id": preview.preview_id,
            "intent": intent.model_dump(mode="json"),
            "missing": [],
            "question": None,
            "assumed": assumed,
            "preview": preview.model_dump(mode="json"),
            "approval_state": preview.approval_state,
            "execution_available": False,
            "note": (
                "Preview only. Explicit approval and a separately authorized execution "
                "rail are required before any submission."
            ),
        }


#: Error kinds that a caller may safely retry (rate limit, server, transport).
#: Cause and retryability are orthogonal: "server" describes what went wrong,
#: "retryable" describes whether trying again makes sense. Keeping them as
#: separate fields avoids collapsing a cause taxonomy into an action word.
_RETRYABLE_KINDS = {"rate_limit", "server", "transport"}


def _observe_error(exc: ZerionAPIError) -> Dict[str, Any]:
    """Typed, credential-free observe failure. No fixture fallback happens here."""
    if isinstance(exc, ZerionAPIAuthError):
        kind = "authorization"
    elif isinstance(exc, ZerionAPIBudgetError):
        kind = "budget"
    elif isinstance(exc, ZerionAPIPaymentError):
        # x402 payment rejected or settlement failed. Not retryable blindly:
        # retrying spends money again for the same failure.
        kind = "payment"
    elif isinstance(exc, ZerionAPIRateLimitError):
        kind = "rate_limit"
    elif isinstance(exc, ZerionAPIServerError):
        kind = "server"
    elif isinstance(exc, ZerionAPIPaginationError):
        kind = "pagination"
    elif isinstance(exc, ZerionAPITransportError):
        kind = "transport"
    elif exc.status == 404:
        # List endpoints raise a generic ZerionAPIError(status=404), not a
        # dedicated exception type (list endpoints return empty data, not
        # 404, per Zerion's docs, so a whole class for it was misleading).
        # The "not_found" signal is preserved here by a status check instead.
        kind = "not_found"
    else:
        kind = "api"
    retryable = kind in _RETRYABLE_KINDS
    _error_kind_counts[kind] += 1
    logger.warning(
        "zerion_observe_error boundary=observe source=zerion_api error.kind=%s "
        "retryable=%s http_status=%s",
        kind,
        retryable,
        exc.status,
    )
    return {
        "status": "error",
        "boundary": "observe",
        "source": "zerion_api",
        "error": {
            "kind": kind,
            "retryable": retryable,
            "message": str(exc),
            "http_status": exc.status,
        },
        "fallback": "none",
    }


def default_host(repo_root: Optional[Union[str, Path]] = None) -> ReadOnlyHost:
    if repo_root:
        return ReadOnlyHost(Path(repo_root) / "fixtures" / "portfolio.json")
    packaged_fixture = files("scout_portfolio_manager").joinpath("data/portfolio.json")
    return ReadOnlyHost(str(packaged_fixture))
