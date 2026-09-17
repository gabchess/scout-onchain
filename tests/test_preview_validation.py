import math
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from scout_portfolio_manager.dca import DcaIntent
from scout_portfolio_manager.safety import build_preview

INTENT = DcaIntent(
    asset="ETH",
    amount_usd=300,
    chain="ethereum",
    schedule="one_time",
    source="wallet:0xabc123",
    destination="wallet:0xdef456",
)
EXPIRY = datetime.now(timezone.utc) + timedelta(days=1)


@pytest.mark.parametrize(
    "field,value",
    [
        ("amount_usd", 0),
        ("amount_usd", -1),
        ("expected_output", 0),
        ("expected_output", -1),
        ("fees_usd", -1),
        ("slippage_pct", -1),
        ("max_fee_usd", -1),
    ],
)
def test_preview_rejects_invalid_financial_ranges(field, value):
    kwargs = dict(
        expected_output=0.13, fees_usd=3, slippage_pct=0.5, quote_expiry=EXPIRY, max_fee_usd=5
    )
    if field == "amount_usd":
        intent = INTENT.model_copy(update={"amount_usd": value})
    else:
        intent = INTENT
        kwargs[field] = value
    with pytest.raises(ValidationError):
        build_preview(intent=intent, **kwargs)


@pytest.mark.parametrize("field", ["expected_output", "fees_usd", "slippage_pct", "max_fee_usd"])
def test_preview_rejects_non_finite_values(field):
    kwargs = dict(
        expected_output=0.13, fees_usd=3, slippage_pct=0.5, quote_expiry=EXPIRY, max_fee_usd=5
    )
    kwargs[field] = math.nan
    with pytest.raises(ValidationError):
        build_preview(intent=INTENT, **kwargs)


def test_preview_rejects_max_fee_below_fee():
    with pytest.raises(ValueError, match="max_fee_usd"):
        build_preview(
            intent=INTENT,
            expected_output=0.13,
            fees_usd=3,
            slippage_pct=0.5,
            quote_expiry=EXPIRY,
            max_fee_usd=2,
        )


def test_preview_rejects_timezone_naive_expiry():
    with pytest.raises(ValueError, match="timezone"):
        build_preview(
            intent=INTENT,
            expected_output=0.13,
            fees_usd=3,
            slippage_pct=0.5,
            quote_expiry=datetime(2999, 1, 1, 13),
            max_fee_usd=5,
        )
