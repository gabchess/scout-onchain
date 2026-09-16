"""Arc wallet reads through the Zerion API source, offline.

Zerion serves Arc (chain id ``arc``) through the same positions and transactions
endpoints Scout already reads. Arc pays gas in USDC. These tests replay a
Zerion-shaped Arc fixture through the real reader and host, with no network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.test_zerion_prepare import NOW, Provider

from scout_portfolio_manager.analytics import drawdown_from_cost_basis_pct
from scout_portfolio_manager.host import ReadOnlyHost
from scout_portfolio_manager.zerion_api import (
    API_KEY_ENV,
    CHAIN_ENV,
    WALLET_ENV,
    ZerionAPIConfig,
    ZerionAPIReader,
    ZerionWalletReader,
    reader_from_env,
)
from scout_portfolio_manager.zerion_prepare import PreparationIntent, PreparationService

ROOT = Path(__file__).resolve().parents[1]
ARC_FIXTURE = json.loads((ROOT / "fixtures" / "zerion" / "arc_wallet.json").read_text())
WALLET = ARC_FIXTURE["wallet_address"]
KEY_FIELD = "api" + "_key"


def arc_transport():
    """Serve the fixture by endpoint and cursor; record every requested URL."""
    pages = ARC_FIXTURE["transaction_pages"]
    by_url = {pages[0]["links"]["next"]: pages[1]}
    urls: list[str] = []

    def transport(request, timeout):
        url = request.full_url
        urls.append(url)
        if "/positions/" in url:
            return ARC_FIXTURE["positions"]
        return by_url.get(url, pages[0])

    transport.urls = urls  # type: ignore[attr-defined]
    return transport


def arc_host(tmp_path, transport=None):
    reader = ZerionAPIReader(
        ZerionAPIConfig(**{KEY_FIELD: "test-key"}), transport=transport or arc_transport()
    )
    return ReadOnlyHost(
        ZerionWalletReader(reader, WALLET, "arc"),
        price_history_path=ROOT / "fixtures" / "price_history.json",
        alerts_path=tmp_path / "alerts.json",
    )


def test_arc_positions_and_transactions_map_without_a_chain_filter(caplog):
    transport = arc_transport()
    reader = ZerionAPIReader(ZerionAPIConfig(**{KEY_FIELD: "test-key"}), transport=transport)

    with caplog.at_level("WARNING"):
        snapshot = reader.snapshot(WALLET, "arc")

    assert snapshot.chain == "arc"
    assert [(h.asset, h.quantity, h.value_usd) for h in snapshot.holdings] == [
        ("USDC", 1500.0, 1500.0),
        ("EURC", 1000.0, 1170.0),
        ("USDC", 500.0, 500.0),
    ]
    assert "UNPRICED" in caplog.text  # an unpriced Arc token is skipped, never invented
    assert [(t.kind, t.asset, t.value_usd, t.fee_usd) for t in snapshot.transactions] == [
        ("sell", "USDC", 1000.0, 0.01),  # Arc gas is paid in USDC
        ("buy", "EURC", 1150.0, 0.0),
        ("transfer", "USDC", 2500.0, 0.0),
        ("sell", "ETH", 500.0, 0.02),
        ("buy", "USDC", 500.0, 0.0),
    ]
    assert len(transport.urls) == 3  # positions plus two transaction pages
    assert not any("chain" in url for url in transport.urls)


def test_arc_wallet_via_env_needs_only_the_existing_variables():
    env = {API_KEY_ENV: "user-supplied-key", WALLET_ENV: WALLET, CHAIN_ENV: "arc"}
    wallet_reader = reader_from_env(env, transport=arc_transport())

    assert wallet_reader is not None
    snapshot = wallet_reader.snapshot()
    assert snapshot.chain == "arc"
    assert snapshot.wallet_address == WALLET


def test_same_symbol_on_two_chains_yields_one_pnl_row(tmp_path):
    result = arc_host(tmp_path).get_pnl()

    assert result["status"] == "ok"
    by_asset = {row["asset"]: row for row in result["results"]}
    assert [row["asset"] for row in result["results"]] == ["USDC", "EURC"]
    usdc = by_asset["USDC"]
    assert usdc["realized_usd"] == 500.0
    assert usdc["unrealized_usd"] == 2000.0
    assert usdc["total_usd"] == 2500.0
    eurc = by_asset["EURC"]
    assert eurc["unrealized_usd"] == 20.0
    assert eurc["realized_usd"] == 0.0
    assert result["unknown"] == []


def test_arc_risk_groups_usdc_across_chains(tmp_path):
    result = arc_host(tmp_path).get_portfolio_risk(shock_pct=-10)

    assert result["status"] == "ok"
    assert result["gross_observed_value_usd"] == 3170.0
    assert result["top_exposure"]["asset"] == "USDC"
    assert result["top_exposure"]["value_usd"] == 2000.0
    assert result["scenario"]["value_after_shock_usd"] == pytest.approx(2853.0)
    assert result["execution_available"] is False


def test_arc_analysis_uses_the_whole_asset_position(tmp_path):
    host = arc_host(tmp_path)

    usdc = host.analyze_asset("USDC")
    assert usdc["status"] == "ok"
    assert usdc["indicators"]["drawdown_from_cost_basis_pct"] == round(
        drawdown_from_cost_basis_pct(2000.0, 500.0), 4
    )
    assert "no price history observed for USDC" in usdc["unknown"]

    eurc = host.dca_windows("EURC")
    assert eurc["status"] == "ok"


def test_arc_report_alerts_and_proposals_stay_read_only(tmp_path):
    host = arc_host(tmp_path)

    report = host.build_report_data()
    assert report["status"] == "ok"
    assert set(report["analyses"]) == {"USDC", "EURC"}

    host.set_alert("USDC", "price_pct_below_cost_basis", 5)
    assert host.check_alerts()["status"] == "ok"

    preview = host.preview_dca(
        "buy $25 of USDC weekly on arc from wallet:main to wallet:main",
        expected_output=24.99,
        fees_usd=0.01,
    )
    assert preview["status"] == "preview_ready"
    assert preview["preview"]["chain"] == "arc"
    assert preview["execution_available"] is False

    plan = host.plan_zerion_action("transfer", "USDC", 10, "arc", "wallet:main")
    assert plan["status"] == "proposal_only"
    assert plan["execution_available"] is False

    knowledge = host.search_defi_knowledge("Arc USDC gas fees")
    assert knowledge["status"] == "ok"


@pytest.mark.parametrize("field", ["chain", "destination_chain"])
def test_preparation_refuses_arc_until_it_is_reviewed(field):
    fields = dict(
        action="bridge",
        chain="base",
        destination_chain="ethereum",
        source_wallet="0x" + "1" * 40,
        destination="0x" + "1" * 40,
        asset="native",
        target_asset="native",
        amount="1",
    )
    fields[field] = "arc"

    with pytest.raises(ValueError, match="Arc is read-only in Scout"):
        PreparationIntent(**fields)


def test_host_preparation_refuses_arc_before_any_provider_call(tmp_path):
    host = arc_host(tmp_path)
    provider = Provider()
    host.preparation = PreparationService(provider, tmp_path / "db", clock=lambda: NOW)

    with pytest.raises(ValueError, match="Arc is read-only in Scout"):
        host.call_tool(
            "prepare_zerion_transaction",
            dict(
                request_id="arc-refused",
                action="transfer",
                chain="arc",
                source_wallet="0x" + "1" * 40,
                destination="0x" + "2" * 40,
                asset="native",
                amount="1",
            ),
        )
    assert provider.calls == 0
