from pathlib import Path

from scout_portfolio_manager.host import ReadOnlyHost

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "portfolio.json"


def _host(tmp_path) -> ReadOnlyHost:
    return ReadOnlyHost(FIXTURE, alerts_path=tmp_path / "alerts.json")


def test_set_alert_then_check_alerts_end_to_end(tmp_path):
    host = _host(tmp_path)
    set_result = host.set_alert("ETH", "rsi_below", 30.0)
    assert set_result["status"] == "ok"
    assert set_result["boundary"] == "propose"
    assert set_result["rule"]["asset"] == "ETH"
    assert set_result["rule_count"] == 1

    check_result = host.check_alerts()
    assert check_result["status"] == "ok"
    assert check_result["boundary"] == "calculate"
    assert check_result["not_financial_advice"] == "This is analysis, not financial advice."
    # ETH's synthetic fixture RSI is well under 30 by design (TA-01's fixture).
    assert len(check_result["fired"]) == 1
    assert check_result["fired"][0]["asset"] == "ETH"
    assert check_result["not_fired"] == []
    assert check_result["unknown"] == []


def test_check_alerts_price_pct_below_cost_basis_rule(tmp_path):
    host = _host(tmp_path)
    host.set_alert("ETH", "price_pct_below_cost_basis", 5.0)
    result = host.check_alerts()
    # Fixture holding is +12.5% above cost basis, so this rule does not fire.
    assert result["not_fired"][0]["asset"] == "ETH"
    assert result["fired"] == []


def test_check_alerts_unknown_asset_lands_in_unknown_not_silently_dropped(tmp_path):
    host = _host(tmp_path)
    host.set_alert("NOSUCHASSET", "rsi_below", 30.0)
    result = host.check_alerts()
    assert result["fired"] == []
    assert result["not_fired"] == []
    assert len(result["unknown"]) == 1
    assert "NOSUCHASSET" in result["unknown"][0]


def test_check_alerts_filters_by_asset(tmp_path):
    host = _host(tmp_path)
    host.set_alert("ETH", "rsi_below", 30.0)
    host.set_alert("NOSUCHASSET", "rsi_below", 30.0)
    result = host.check_alerts(asset="ETH")
    assert len(result["fired"]) + len(result["not_fired"]) == 1
    assert result["unknown"] == []


def test_check_alerts_observes_wallet_once_for_all_rules(tmp_path):
    from scout_portfolio_manager.portfolio import FixturePortfolioReader

    class CountingReader:
        def __init__(self):
            self.calls = 0
            self.fixture = FixturePortfolioReader(FIXTURE)

        def snapshot(self):
            self.calls += 1
            return self.fixture.snapshot()

    reader = CountingReader()
    host = ReadOnlyHost(reader, alerts_path=tmp_path / "alerts.json")
    host.set_alert("ETH", "rsi_below", 30.0)
    host.set_alert("ETH", "rsi_below", 40.0)

    host.check_alerts()
    assert reader.calls == 1


def test_no_daemon_or_background_thread_is_created(tmp_path):
    import threading

    before = threading.active_count()
    host = _host(tmp_path)
    host.set_alert("ETH", "rsi_below", 30.0)
    host.check_alerts()
    assert threading.active_count() == before
