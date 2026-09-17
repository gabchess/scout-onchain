from datetime import datetime, timedelta, timezone

import pytest

from scout_portfolio_manager.dca import DcaIntent
from scout_portfolio_manager.safety import PreviewInputError, build_preview


def _future() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=1)


def test_preview_contains_all_material_transaction_fields_and_requires_approval():
    expiry = _future()
    preview = build_preview(
        intent=DcaIntent(
            asset="ETH",
            amount_usd=300,
            chain="ethereum",
            schedule="one_time",
            source="wallet:0xabc123",
            destination="wallet:0xdef456",
        ),
        expected_output=0.13,
        fees_usd=3.0,
        slippage_pct=0.5,
        quote_expiry=expiry,
        max_fee_usd=5,
    )
    assert preview.approval_state == "required"
    assert preview.asset == "ETH"
    assert preview.amount_usd == 300
    assert preview.currency == "USD"
    assert preview.chain == "ethereum"
    assert preview.source == "wallet:0xabc123"
    assert preview.destination == "wallet:0xdef456"
    assert preview.expected_output == 0.13
    assert preview.fees_usd == 3
    assert preview.slippage_pct == 0.5
    assert preview.quote_expiry == expiry
    assert preview.schedule == "one_time"
    assert preview.max_fee_usd == 5
    assert "settlement" in preview.failure_behavior.lower()


def test_build_preview_mints_preview_id():
    intent = DcaIntent(
        asset="ETH",
        amount_usd=100.0,
        chain="ethereum",
        schedule="weekly",
        source="wallet:0xabc",
        destination="wallet:0xdef",
    )
    a = build_preview(
        intent=intent,
        expected_output=0.04,
        fees_usd=1.0,
        slippage_pct=0.5,
        quote_expiry=_future(),
        max_fee_usd=5.0,
    )
    b = build_preview(
        intent=intent,
        expected_output=0.04,
        fees_usd=1.0,
        slippage_pct=0.5,
        quote_expiry=_future(),
        max_fee_usd=5.0,
    )
    assert isinstance(a.preview_id, str) and a.preview_id
    assert a.preview_id != b.preview_id


@pytest.mark.parametrize("offset", [timedelta(0), timedelta(seconds=-1), timedelta(days=-400)])
def test_build_preview_rejects_expired_quote(offset):
    intent = DcaIntent(
        asset="ETH",
        amount_usd=100.0,
        chain="ethereum",
        schedule="weekly",
        source="wallet:0xabc",
        destination="wallet:0xdef",
    )
    with pytest.raises(PreviewInputError) as caught:
        build_preview(
            intent=intent,
            expected_output=0.04,
            fees_usd=1.0,
            slippage_pct=0.5,
            quote_expiry=datetime.now(timezone.utc) + offset,
            max_fee_usd=5.0,
        )
    assert caught.value.field == "quote_expiry"
