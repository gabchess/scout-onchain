import math
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .dca import DcaIntent


class DcaPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str
    amount_usd: float = Field(gt=0)
    currency: Literal["USD"]
    chain: str
    source: str
    destination: str
    expected_output: float = Field(gt=0)
    fees_usd: float = Field(ge=0)
    slippage_pct: float = Field(ge=0)
    quote_expiry: datetime
    schedule: str
    max_fee_usd: Optional[float] = Field(default=None, ge=0)
    approval_state: Literal["required"]
    preview_id: str
    failure_behavior: str

    @field_validator("amount_usd", "expected_output", "fees_usd", "slippage_pct", "max_fee_usd")
    @classmethod
    def require_finite_numbers(cls, value):
        if value is not None and not math.isfinite(value):
            raise ValueError("financial values must be finite")
        return value

    @field_validator("quote_expiry")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("quote_expiry must include a timezone")
        return value

    @model_validator(mode="after")
    def max_fee_covers_fee(self):
        if self.max_fee_usd is not None and self.max_fee_usd < self.fees_usd:
            raise ValueError("max_fee_usd must be at least fees_usd")
        return self


class PreviewInputError(ValueError):
    """A preview input failed validation. ``field`` names the input, never its value."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


def build_preview(
    *,
    intent: DcaIntent,
    expected_output: float,
    fees_usd: float,
    slippage_pct: float,
    quote_expiry: datetime,
    max_fee_usd: Optional[float],
) -> DcaPreview:
    if any(
        value is None or value == ""
        for value in (
            intent.asset,
            intent.amount_usd,
            intent.chain,
            intent.schedule,
            intent.source,
            intent.destination,
        )
    ):
        raise ValueError("complete DCA intent required for preview")
    if quote_expiry.tzinfo is None or quote_expiry.utcoffset() is None:
        raise PreviewInputError("quote_expiry", "quote_expiry must include a timezone")
    if quote_expiry <= datetime.now(timezone.utc):
        raise PreviewInputError("quote_expiry", "quote_expiry must be in the future")
    # The completeness guard above establishes these fields for type checkers.
    assert intent.asset is not None
    assert intent.amount_usd is not None
    assert intent.chain is not None
    assert intent.schedule is not None
    assert intent.source is not None
    assert intent.destination is not None
    return DcaPreview(
        asset=intent.asset,
        amount_usd=intent.amount_usd,
        currency="USD",
        chain=intent.chain,
        source=intent.source,
        destination=intent.destination,
        expected_output=expected_output,
        fees_usd=fees_usd,
        slippage_pct=slippage_pct,
        quote_expiry=quote_expiry,
        schedule=intent.schedule,
        max_fee_usd=max_fee_usd,
        approval_state="required",
        preview_id=str(uuid.uuid4()),
        failure_behavior=(
            "If the quote expires or settlement fails, do not report success; "
            "surface the failure for review."
        ),
    )
