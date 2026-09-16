import re
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DcaIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: Optional[str] = None
    amount_usd: Optional[float] = None
    chain: Optional[str] = None
    schedule: Optional[str] = None
    source: Optional[str] = None
    destination: Optional[str] = None


class DcaParseResult(BaseModel):
    intent: DcaIntent
    status: str
    missing: List[str]
    question: Optional[str] = None
    #: Per filled field: "regex", "synonym" or "model_selected" (ADR 0004 D-9.5).
    field_sources: Dict[str, str] = Field(default_factory=dict)


def _single_match(pattern: str, text: str, *, flags: int = re.I) -> Optional[str]:
    matches = re.findall(pattern, text, flags)
    return matches[0] if len(matches) == 1 else None


def _single_amount(text: str) -> Optional[float]:
    matches = re.findall(r"\$(\d+(?:\.\d+)?)", text)
    return float(matches[0]) if len(matches) == 1 else None


def parse_dca_request(text: str) -> DcaParseResult:
    asset = _single_match(r"\b(ETH|BTC|USDC|SOL)\b", text)
    amount_usd = _single_amount(text)
    chain = _single_match(r"\bon\s+([a-z][a-z0-9-]*)", text)
    schedule = _single_match(r"\b(one[- ]?time|daily|weekly|monthly)\b", text)
    source = _single_match(r"\bfrom\s+(wallet:[^\s]+|rail:[^\s]+)", text)
    destination = _single_match(r"\bto\s+(wallet:[^\s]+|rail:[^\s]+)", text)
    intent = DcaIntent(
        asset=asset.upper() if asset else None,
        amount_usd=amount_usd,
        chain=chain.lower() if chain else None,
        schedule=schedule.lower().replace("-", "_").replace(" ", "_") if schedule else None,
        source=source,
        destination=destination,
    )
    missing = [
        name
        for name in ("asset", "amount_usd", "chain", "schedule", "source", "destination")
        if getattr(intent, name) is None
    ]
    question = f"Which {missing[0].replace('_', ' ')} should I use?" if missing else None
    return DcaParseResult(
        intent=intent,
        status="needs_clarification" if missing else "ready",
        missing=missing,
        question=question,
        field_sources={
            name: "regex"
            for name in ("asset", "amount_usd", "chain", "schedule", "source", "destination")
            if getattr(intent, name) is not None
        },
    )
