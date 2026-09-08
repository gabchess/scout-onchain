"""User-defined alert rules, evaluated strictly on demand. No daemon, no cron, no push.

AlertStore persists rules to one local JSON file so a fresh `/loop` process
(one process per tick) doesn't silently forget every rule between ticks. No
locking: this store supports single-process, on-demand use only.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict


class AlertRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    asset: str
    kind: Literal["price_pct_below_cost_basis", "rsi_below"]
    threshold: float
    created_at: datetime


class AlertStore:
    """Reads/writes one JSON file of AlertRule records."""

    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)

    def _read_all(self) -> List[AlertRule]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text() or "[]")
        return [AlertRule.model_validate(item) for item in raw]

    def _write_all(self, rules: List[AlertRule]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps([r.model_dump(mode="json") for r in rules], indent=2)
        self.path.write_text(payload)

    def add(self, *, asset: str, kind: str, threshold: float) -> AlertRule:
        rules = self._read_all()
        rule = AlertRule(
            id=str(uuid.uuid4()),
            asset=asset.upper(),
            kind=kind,  # type: ignore[arg-type]
            threshold=threshold,
            created_at=datetime.now(timezone.utc),
        )
        rules.append(rule)
        self._write_all(rules)
        return rule

    def list(self, asset: Optional[str] = None) -> List[AlertRule]:
        rules = self._read_all()
        if asset is None:
            return rules
        target = asset.upper()
        return [r for r in rules if r.asset == target]


def evaluate_alert(
    rule: AlertRule, *, analysis: Dict[str, Any], pnl: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Evaluate one rule against already-computed analyze_asset/get_pnl output.

    "stale" is always reported when known, taken from analysis["freshness"],
    never used to suppress or force the fire/no-fire decision.
    """
    freshness = analysis.get("freshness") or {}
    stale = bool(freshness.get("stale", False))

    observed_value: Optional[float] = None
    fired = False
    if rule.kind == "rsi_below":
        observed_value = analysis.get("indicators", {}).get("rsi_14")
        if observed_value is not None:
            fired = observed_value < rule.threshold
    elif rule.kind == "price_pct_below_cost_basis":
        drawdown = None
        if pnl is not None:
            for result in pnl.get("results", []):
                if result.get("asset") == rule.asset:
                    drawdown = result.get("return_pct")
                    break
        observed_value = drawdown
        if observed_value is not None:
            fired = observed_value < -rule.threshold

    return {
        "rule_id": rule.id,
        "asset": rule.asset,
        "kind": rule.kind,
        "threshold": rule.threshold,
        "observed_value": observed_value,
        "fired": fired,
        "stale": stale,
    }
