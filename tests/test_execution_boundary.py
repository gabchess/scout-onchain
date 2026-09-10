"""Mechanical gates for Scout's public no-trade boundary."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "scout_portfolio_manager"

EXPECTED_TOOLS = frozenset(
    {
        "get_portfolio_snapshot",
        "get_pnl",
        "parse_dca_request",
        "preview_dca",
        "analyze_asset",
        "dca_windows",
        "set_alert",
        "check_alerts",
        "get_portfolio_risk",
        "assess_defi_yield",
        "search_defi_knowledge",
        "plan_zerion_action",
        "prepare_zerion_transaction",
        "get_zerion_preparation",
    }
)


def test_no_execution_adapter_ships_in_the_runtime():
    assert not (SRC / "adapters.py").exists()


def test_mcp_server_tool_registry_is_pinned_to_the_public_tools():
    mcp = pytest.importorskip("mcp", reason="mcp extra not installed")
    del mcp
    from scout_portfolio_manager.host import default_host
    from scout_portfolio_manager.mcp_server import create_server

    server = create_server(default_host())
    tools = asyncio.run(server.list_tools())
    tool_names = {tool.name for tool in tools}
    assert tool_names == EXPECTED_TOOLS
