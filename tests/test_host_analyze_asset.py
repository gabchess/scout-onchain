import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scout_portfolio_manager.contracts import (
    Holding,
    PortfolioSnapshot,
    SourceMetadata,
    Transaction,
)
from scout_portfolio_manager.host import ReadOnlyHost

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "portfolio.json"
PRICE_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "price_history.json"


def _snapshot(*, observed_at=None, holdings=None, transactions=None) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        wallet_address="0xabc123",
        chain="ethereum",
        observed_at=observed_at or datetime(2026, 9, 3, 12, tzinfo=timezone.utc),
        source=SourceMetadata(
            kind="fixture", locator="test", retrieved_at=datetime(2026, 9, 3, tzinfo=timezone.utc)
        ),
        holdings=(
            holdings if holdings is not None else [Holding(asset="ETH", quantity=1, value_usd=2250)]
        ),
        transactions=transactions
        if transactions is not None
        else [
            Transaction(
                id="buy-1",
                kind="buy",
                asset="ETH",
                quantity=1,
                value_usd=2000,
                occurred_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
                wallet_address="0xabc123",
            )
        ],
    )


class _FakeReader:
    def __init__(self, snapshot: PortfolioSnapshot):
        self._snapshot = snapshot

    def snapshot(self) -> PortfolioSnapshot:
        return self._snapshot


@pytest.fixture
def host() -> ReadOnlyHost:
    return ReadOnlyHost(FIXTURE)


def test_analyze_asset_ok_path_against_real_fixtures(host: ReadOnlyHost):
    result = host.analyze_asset("ETH")
    assert result["status"] == "ok"
    assert result["boundary"] == "calculate"
    assert result["asset"] == "ETH"
    assert result["unknown"] == []
    assert result["confidence"] == "low"
    assert (
        result["disclosure"]
        == "Heuristic indicators, not backtested; treat as descriptive, not predictive."
    )
    indicators = result["indicators"]
    assert set(indicators) == {
        "sma_20",
        "ema_12",
        "rsi_14",
        "range_30d",
        "distance_from_range_pct",
        "drawdown_from_cost_basis_pct",
    }
    assert indicators["drawdown_from_cost_basis_pct"] == 12.5
    assert result["freshness"] == {
        "stale": False,
        "max_age_days": 2,
        "last_price_date": "2026-09-03",
    }


def test_analyze_asset_lowercases_input_is_accepted(host: ReadOnlyHost):
    result = host.analyze_asset("eth")
    assert result["asset"] == "ETH"
    assert result["status"] == "ok"


def test_analyze_asset_missing_basis_path(host: ReadOnlyHost):
    # ETH has price history, but zero buy transactions means no acquisition basis.
    snapshot = _snapshot(transactions=[])
    fake_host = ReadOnlyHost(_FakeReader(snapshot), price_history_path=PRICE_FIXTURE)
    result = fake_host.analyze_asset("ETH")
    assert result["status"] == "ok"
    assert "missing acquisition basis for ETH" in result["unknown"]
    assert "drawdown_from_cost_basis_pct" not in result["indicators"]
    # Price-derived indicators still resolve independently of basis.
    assert "rsi_14" in result["indicators"]


def test_analyze_asset_missing_price_history_path(host: ReadOnlyHost):
    result = host.analyze_asset("NOSUCHASSET")
    assert result["status"] == "ok"
    assert "no price history observed for NOSUCHASSET" in result["unknown"]
    assert "missing acquisition basis for NOSUCHASSET" in result["unknown"]
    assert result["indicators"] == {}
    assert "freshness" not in result


def test_analyze_asset_flags_stale_price_data(tmp_path):
    # Build a price-history fixture whose last observed date is well before
    # the snapshot's observed_at date.
    stale_fixture = tmp_path / "price_history.json"
    raw = json.loads(PRICE_FIXTURE.read_text())
    stale_fixture.write_text(json.dumps(raw))
    snapshot = _snapshot(observed_at=datetime(2026, 9, 20, 12, tzinfo=timezone.utc))
    fake_host = ReadOnlyHost(_FakeReader(snapshot), price_history_path=stale_fixture)
    result = fake_host.analyze_asset("ETH")
    assert result["freshness"]["stale"] is True
    assert result["freshness"]["last_price_date"] == "2026-09-03"


def test_analyze_asset_confidence_is_always_low(host: ReadOnlyHost):
    assert host.analyze_asset("ETH")["confidence"] == "low"
    assert host.analyze_asset("NOSUCHASSET")["confidence"] == "low"


def test_analyze_asset_surfaces_fixture_price_history_source(host):
    result = host.analyze_asset("ETH")
    assert result["status"] == "ok"
    src = result["price_history_source"]
    assert src["kind"] == "fixture"
    assert "synthetic" in src["locator"].lower() or "fixture" in src["locator"].lower()
