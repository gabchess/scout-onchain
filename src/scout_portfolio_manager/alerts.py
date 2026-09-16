"""User-defined alert rules, evaluated strictly on demand. No daemon, no cron, no push.

AlertStore persists rules to one local JSON file so a fresh `/loop` process
(one process per tick) doesn't silently forget every rule between ticks. No
locking: this store supports single-process, on-demand use only.

The default file is `ZPM_ALERTS_PATH` when set, else `~/.scout/alerts.json`.
Host launchers start the server from an arbitrary, possibly read-only, working
directory, so the default never depends on the cwd.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional, Union

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

#: Pre-0.7 default, relative to the process working directory.
LEGACY_ALERTS_PATH = Path(".scout") / "alerts.json"


def default_alerts_path(environ: Optional[Mapping[str, str]] = None) -> Path:
    """Return `ZPM_ALERTS_PATH` if set and non-empty, else `~/.scout/alerts.json`."""
    env = os.environ if environ is None else environ
    override = env.get("ZPM_ALERTS_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".scout" / "alerts.json"


class AlertRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    asset: str
    kind: Literal["price_pct_below_cost_basis", "rsi_below"]
    threshold: float
    created_at: datetime


class AlertStore:
    """Reads/writes one JSON file of AlertRule records."""

    def __init__(
        self, path: Union[str, Path], *, legacy_path: Optional[Union[str, Path]] = None
    ) -> None:
        self.path = Path(path)
        self.legacy_path = Path(legacy_path) if legacy_path is not None else None
        self._legacy_notice_sent = False

    @staticmethod
    def _load(path: Path) -> List[AlertRule]:
        raw = json.loads(path.read_text() or "[]")
        return [AlertRule.model_validate(item) for item in raw]

    def _read_all(self) -> List[AlertRule]:
        legacy = self.legacy_path
        has_legacy = (
            legacy is not None and legacy.exists() and legacy.resolve() != self.path.resolve()
        )
        if self.path.exists():
            if has_legacy and not self._legacy_notice_sent:
                self._legacy_notice_sent = True
                logger.warning(
                    "alerts: ignoring legacy %s because %s already exists. "
                    "Set ZPM_ALERTS_PATH to use the legacy file.",
                    legacy,
                    self.path,
                )
            return self._load(self.path)
        if not has_legacy or legacy is None:
            return []
        rules = self._load(legacy)
        logger.warning(
            "alerts: copied %d rule(s) from legacy %s to %s; the old file is kept. "
            "Set ZPM_ALERTS_PATH to choose another location.",
            len(rules),
            legacy,
            self.path,
        )
        self._write_all(rules)
        return rules

    def _write_all(self, rules: List[AlertRule]) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = json.dumps([r.model_dump(mode="json") for r in rules], indent=2)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(payload)
        os.chmod(self.path, 0o600)

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
