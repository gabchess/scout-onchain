from pathlib import Path
from types import SimpleNamespace

import pytest

from scout_portfolio_manager.host import ReadOnlyHost
from scout_portfolio_manager.reporting_html import build_report, render_report

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "portfolio.json"


def _host() -> ReadOnlyHost:
    return ReadOnlyHost(FIXTURE)


def _built_inputs(host: ReadOnlyHost):
    snapshot = host.get_portfolio_snapshot()["snapshot"]
    pnl = host.get_pnl()
    analyses = {h["asset"]: host.analyze_asset(h["asset"]) for h in snapshot["holdings"]}
    windows = {h["asset"]: host.dca_windows(h["asset"]) for h in snapshot["holdings"]}
    alerts = host.check_alerts()
    return snapshot, pnl, analyses, windows, alerts


def test_render_report_contains_wallet_address_and_pnl_total():
    host = _host()
    snapshot, pnl, analyses, windows, alerts = _built_inputs(host)
    html = render_report(
        snapshot=snapshot, pnl=pnl, analyses=analyses, windows=windows, alerts=alerts
    )
    assert "<html" in html and "</html>" in html
    assert snapshot["wallet_address"] in html
    total_usd = sum(r["total_usd"] for r in pnl["results"])
    assert f"{total_usd:,.2f}" in html


def test_render_report_contains_each_analyzed_assets_rsi_value():
    host = _host()
    snapshot, pnl, analyses, windows, alerts = _built_inputs(host)
    html = render_report(
        snapshot=snapshot, pnl=pnl, analyses=analyses, windows=windows, alerts=alerts
    )
    for analysis in analyses.values():
        rsi = analysis["indicators"].get("rsi_14")
        if rsi is not None:
            assert str(rsi) in html


def test_render_report_contains_dca_windows_label():
    host = _host()
    snapshot, pnl, analyses, windows, alerts = _built_inputs(host)
    html = render_report(
        snapshot=snapshot, pnl=pnl, analyses=analyses, windows=windows, alerts=alerts
    )
    for window in windows.values():
        assert window["label"] in html


def test_render_report_empty_alerts_state():
    host = _host()
    snapshot, pnl, analyses, windows, alerts = _built_inputs(host)
    assert alerts["fired"] == [] and alerts["not_fired"] == []
    html = render_report(
        snapshot=snapshot, pnl=pnl, analyses=analyses, windows=windows, alerts=alerts
    )
    assert "No alert rules are set" in html


def test_render_report_shows_fired_alert_when_a_rule_is_set(tmp_path):
    host = ReadOnlyHost(FIXTURE, alerts_path=tmp_path / "alerts.json")
    host.set_alert("ETH", "rsi_below", 90.0)  # deliberately loose: fires against the fixture
    snapshot, pnl, analyses, windows, alerts = _built_inputs(host)
    assert len(alerts["fired"]) == 1
    html = render_report(
        snapshot=snapshot, pnl=pnl, analyses=analyses, windows=windows, alerts=alerts
    )
    assert "FIRED" in html
    assert "No alert rules are set" not in html


def test_render_report_carries_pinned_strings_verbatim():
    host = _host()
    snapshot, pnl, analyses, windows, alerts = _built_inputs(host)
    html = render_report(
        snapshot=snapshot, pnl=pnl, analyses=analyses, windows=windows, alerts=alerts
    )
    assert "This is analysis, not financial advice." in html
    assert (
        "Heuristic indicators, not backtested; treat as descriptive, not predictive." in html
    )


def test_render_report_performs_no_network_or_fetch_markup():
    host = _host()
    snapshot, pnl, analyses, windows, alerts = _built_inputs(host)
    html = render_report(
        snapshot=snapshot, pnl=pnl, analyses=analyses, windows=windows, alerts=alerts
    )
    assert "fetch(" not in html
    assert "<script" not in html
    assert 'src="http' not in html
    assert 'href="http' not in html


def test_build_report_runs_the_full_chain_against_real_fixtures():
    host = _host()
    html = build_report(host)
    assert "<html" in html
    assert "ETH" in html


def test_build_report_blocks_x402_without_a_cumulative_budget():
    fake_reader = SimpleNamespace(authorization_mode="x402")
    host = ReadOnlyHost(fake_reader)

    with pytest.raises(RuntimeError, match="no cumulative spend budget"):
        build_report(host)
