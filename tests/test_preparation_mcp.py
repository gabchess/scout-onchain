"""MCP preparation wiring, with provider calls counted at the real transport boundary."""

from __future__ import annotations

import asyncio
import json

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from tests.test_zerion_prepare import NOW, TARGET, TOKEN, WALLET, Provider

from scout_portfolio_manager.host import default_host
from scout_portfolio_manager.mcp_server import create_server
from scout_portfolio_manager.zerion_prepare import PreparationService


def test_mcp_strict_input_before_provider_and_durable_status(tmp_path):
    async def run():
        provider = Provider()
        host = default_host()
        host.preparation = PreparationService(provider, tmp_path / "db", clock=lambda: NOW)
        server = create_server(host)
        payload = dict(
            request_id="mcp-id",
            action="swap",
            chain="base",
            source_wallet=WALLET,
            asset=TOKEN,
            amount="100",
            target_asset=TARGET,
        )
        for change in (
            {"amount": 100},
            {"amount": True},
            {"slippage_bps": True},
            {"action": "execute"},
            {"asset": "USDC"},
        ):
            with pytest.raises(ToolError):
                await server.call_tool("prepare_zerion_transaction", payload | change)
        assert provider.calls == 0
        result = await server.call_tool("prepare_zerion_transaction", payload)
        assert "prepared_unsigned" in str(result)
        assert provider.calls == 1
        result = await server.call_tool("get_zerion_preparation", {"request_id": "mcp-id"})
        assert "prepared_unsigned" in str(result)
        assert provider.calls == 1
        tool = next(t for t in await server.list_tools() if t.name == "plan_zerion_action")
        assert "swap" in tool.inputSchema["properties"]["action"]["enum"]

    asyncio.run(run())


def test_default_registry_preparation_is_disabled():
    host = default_host()
    result = host.call_tool(
        "prepare_zerion_transaction",
        dict(
            request_id="off",
            action="swap",
            chain="base",
            source_wallet=WALLET,
            asset=TOKEN,
            amount="1",
            target_asset=TARGET,
        ),
    )
    assert result["status"] == "disabled"
    assert (
        json.loads(json.dumps(host.call_tool("get_zerion_preparation", {"request_id": "off"})))[
            "status"
        ]
        == "disabled"
    )
