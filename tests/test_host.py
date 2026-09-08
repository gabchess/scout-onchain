import logging
from pathlib import Path

import pytest

from scout_portfolio_manager import __version__
from scout_portfolio_manager.host import (
    DEFAULT_ETH_USD,
    TOOL_NAMES,
    ReadOnlyHost,
    default_host,
    error_kind_counts,
)
from scout_portfolio_manager.zerion_api import (
    ZerionAPIAuthError,
    ZerionAPIBudgetError,
    ZerionAPIError,
    ZerionAPIPaginationError,
    ZerionAPIRateLimitError,
    ZerionAPIServerError,
    ZerionAPITransportError,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "portfolio.json"


@pytest.fixture
def host() -> ReadOnlyHost:
    return ReadOnlyHost(FIXTURE)


def test_tool_manifest_is_read_only_and_complete(host: ReadOnlyHost):
    names = [tool["name"] for tool in host.tool_manifest()]
    assert names == list(TOOL_NAMES)
    assert "execute" not in names
    assert "execute_dca" not in names


def test_tool_manifest_entries_carry_a_version(host: ReadOnlyHost):
    for tool in host.tool_manifest():
        assert tool["version"] == __version__


def test_get_portfolio_snapshot_observes_fixture(host: ReadOnlyHost):
    result = host.get_portfolio_snapshot()
    assert result["status"] == "ok"
    assert result["boundary"] == "observe"
    assert result["snapshot"]["wallet_address"] == "0xabc123"
    assert result["snapshot"]["holdings"][0]["asset"] == "ETH"
    assert result["snapshot"]["source"]["kind"] == "fixture"


def test_get_pnl_explains_fixture_unrealized_gain(host: ReadOnlyHost):
    result = host.get_pnl()
    assert result["status"] == "ok"
    assert result["boundary"] == "calculate"
    assert len(result["results"]) == 1
    pnl = result["results"][0]
    assert pnl["asset"] == "ETH"
    assert pnl["unrealized_usd"] == 250.0
    assert pnl["return_pct"] == 12.5
    assert result["unknown"] == []


def test_get_pnl_filters_unknown_asset(host: ReadOnlyHost):
    result = host.get_pnl(asset="BTC")
    assert result["results"] == []
    assert "no holding observed for BTC" in result["unknown"]


def test_parse_dca_asks_instead_of_inferring(host: ReadOnlyHost):
    result = host.parse_dca_request("DCA another $300 of ETH")
    assert result["status"] == "needs_clarification"
    assert result["boundary"] == "propose"
    assert "chain" in result["missing"]
    assert "schedule" in result["missing"]
    assert "source" in result["missing"]
    assert "destination" in result["missing"]
    assert result["question"]


def test_parse_dca_ready_when_explicit(host: ReadOnlyHost):
    result = host.parse_dca_request(
        "DCA $300 ETH on ethereum weekly from wallet:0xabc123 to wallet:0xdef456"
    )
    assert result["status"] == "ready"
    assert result["missing"] == []
    assert result["intent"]["amount_usd"] == 300
    assert result["intent"]["destination"] == "wallet:0xdef456"


def test_preview_dca_blocks_incomplete_request(host: ReadOnlyHost):
    result = host.preview_dca("DCA another $300 of ETH")
    assert result["status"] == "needs_clarification"
    assert result["preview"] is None
    assert "preview_id" not in result


def test_preview_dca_boundary_is_approve(host: ReadOnlyHost):
    result = host.preview_dca(
        "DCA $300 ETH on ethereum weekly from wallet:0xabc123 to wallet:0xdef456",
        expected_output=0.13,
        fees_usd=3.0,
        slippage_pct=0.5,
        quote_expiry="2026-09-03T13:00:00+00:00",
        max_fee_usd=5.0,
    )
    assert result["status"] == "preview_ready"
    assert result["boundary"] == "preview"
    assert isinstance(result["preview_id"], str) and result["preview_id"]
    assert result["preview_id"] == result["preview"]["preview_id"]
    assert result["approval_state"] == "required"
    assert result["execution_available"] is False
    preview = result["preview"]
    assert preview["asset"] == "ETH"
    assert preview["amount_usd"] == 300
    assert preview["chain"] == "ethereum"
    assert preview["source"] == "wallet:0xabc123"
    assert preview["destination"] == "wallet:0xdef456"
    assert preview["approval_state"] == "required"


def test_call_tool_dispatches_and_rejects_execute(host: ReadOnlyHost):
    snap = host.call_tool("get_portfolio_snapshot")
    assert snap["boundary"] == "observe"
    with pytest.raises(ValueError, match="unknown tool"):
        host.call_tool("not_a_tool")


@pytest.mark.parametrize("tool_name", ["execute", "execute_dca", "submit", "sign"])
def test_call_tool_permission_error_for_write_names(host: ReadOnlyHost, tool_name: str):
    with pytest.raises(PermissionError, match="not available on the read-only host"):
        host.call_tool(tool_name, {"text": "DCA $300 ETH"})


def test_preview_dca_mints_distinct_preview_ids(host: ReadOnlyHost):
    text = "DCA $300 ETH on ethereum weekly from wallet:0xabc123 to wallet:0xdef456"
    kwargs = dict(
        expected_output=0.13,
        fees_usd=3.0,
        slippage_pct=0.5,
        quote_expiry="2026-09-03T13:00:00+00:00",
        max_fee_usd=5.0,
    )
    a = host.preview_dca(text, **kwargs)
    b = host.preview_dca(text, **kwargs)
    assert a["preview_id"] != b["preview_id"]


def test_default_host_resolves_repo_fixture():
    host = default_host()
    result = host.get_portfolio_snapshot()
    assert result["snapshot"]["holdings"][0]["quantity"] == 1.0


def test_default_host_uses_packaged_fixture():
    host = default_host()
    assert host.get_portfolio_snapshot()["status"] == "ok"


# --- ZPM-058: preview_dca_live assumed-price labeling ------------------------


def test_preview_dca_live_labels_assumed_price_as_fixture_only(host: ReadOnlyHost):
    result = host.preview_dca(
        "DCA $300 ETH on ethereum weekly from wallet:0xabc123 to wallet:0xdef456"
    )
    assert result["status"] == "preview_ready"
    assumed_price_note = next(a for a in result["assumed"] if "expected_output" in a)
    assert "DEFAULT_ETH_USD" in assumed_price_note
    assert str(DEFAULT_ETH_USD) in assumed_price_note
    assert "fixture-only" in assumed_price_note
    assert "never a live quote" in assumed_price_note


# --- ZPM-052 / ZPM-060: error taxonomy + observe_error_logged ----------------


class _FailingReader:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def snapshot(self):
        raise self._exc


@pytest.mark.parametrize(
    "exc, expected_kind",
    [
        (ZerionAPIError("missing", status=404), "not_found"),
        (ZerionAPIError("bad request", status=400), "api"),
        (ZerionAPIServerError("boom", status=503), "server"),
        (ZerionAPIBudgetError("spent"), "budget"),
        (ZerionAPIPaginationError("bad cursor"), "pagination"),
    ],
)
def test_observe_error_maps_new_error_taxonomy_kinds(exc, expected_kind):
    result = ReadOnlyHost(_FailingReader(exc)).get_portfolio_snapshot()
    assert result["status"] == "error"
    assert result["error"]["kind"] == expected_kind


def test_observe_error_not_found_kind():
    exc = ZerionAPIError("Zerion API returned HTTP 404", status=404)
    result = ReadOnlyHost(_FailingReader(exc)).get_portfolio_snapshot()
    assert result["status"] == "error"
    assert result["error"]["kind"] == "not_found"
    assert result["error"]["http_status"] == 404


@pytest.mark.parametrize(
    "exc, expected_retryable",
    [
        (ZerionAPIRateLimitError("limited", status=429), True),
        (ZerionAPIServerError("boom", status=503), True),
        (ZerionAPITransportError("dropped"), True),
        (ZerionAPIAuthError("denied", status=401), False),
        (ZerionAPIBudgetError("spent"), False),
        (ZerionAPIPaginationError("bad cursor"), False),
        (ZerionAPIError("missing", status=404), False),
        (ZerionAPIError("bad request", status=400), False),
    ],
)
def test_observe_error_retryable_flag(exc, expected_retryable):
    result = ReadOnlyHost(_FailingReader(exc)).get_portfolio_snapshot()
    assert result["error"]["retryable"] is expected_retryable


def test_observe_error_logged_emits_structured_log_and_increments_counter(caplog):
    before = error_kind_counts().get("authorization", 0)
    with caplog.at_level(logging.WARNING):
        result = ReadOnlyHost(
            _FailingReader(ZerionAPIAuthError("denied", status=401))
        ).get_portfolio_snapshot()
    assert result["error"]["kind"] == "authorization"

    matching = [r for r in caplog.records if "error.kind=authorization" in r.message]
    assert matching, "expected a structured log line naming error.kind=authorization"

    after = error_kind_counts().get("authorization", 0)
    assert after == before + 1


def test_default_host_packaged_analyze_asset_without_repo_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    host = default_host()
    result = host.analyze_asset("ETH")
    assert result["status"] == "ok"
    assert result.get("price_history_source", {}).get("kind") == "fixture"
