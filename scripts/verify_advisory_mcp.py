"""Exercise the installed Scout package over real stdio MCP with no credential inheritance."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED = {
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


async def verify() -> dict[str, object]:
    # Explicit env deliberately excludes all provider keys and wallet configuration.
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "scout_portfolio_manager.mcp_server"],
        env={"PATH": os.defpath, "PYTHONNOUSERSITE": "1"},
    )
    results: dict[str, object] = {}
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            assert names == EXPECTED, names
            results["tools"] = sorted(names)
            cases: list[tuple[str, dict[str, Any]]] = [
                ("get_portfolio_risk", {"shock_pct": -30}),
                ("assess_defi_yield", {"principal_usd": 1000, "base_apr_pct": 5, "fees_usd": 10}),
                ("search_defi_knowledge", {"query": "PDA", "ecosystem": "solana", "limit": 2}),
                (
                    "plan_zerion_action",
                    {"action": "swap", "asset": "USDC", "amount": 100, "chain": "base"},
                ),
                ("get_pnl", {}),
                ("get_zerion_preparation", {"request_id": "disabled-smoke"}),
                (
                    "prepare_zerion_transaction",
                    {
                        "request_id": "disabled-smoke",
                        "action": "transfer",
                        "chain": "base",
                        "source_wallet": "0x" + "1" * 40,
                        "asset": "native",
                        "amount": "0.001",
                        "destination": "0x" + "2" * 40,
                    },
                ),
            ]
            for name, args in cases:
                response = await session.call_tool(name, args)
                assert not response.isError, response
                block = response.content[0]
                assert block.type == "text"
                results[name] = json.loads(block.text)
            invalid = await session.call_tool("get_portfolio_risk", {"shock_pct": True})
            assert invalid.isError
            results["invalid_boolean_rejected"] = invalid.isError
    risk = results["get_portfolio_risk"]
    assert isinstance(risk, dict)
    assert risk["gross_observed_value_usd"] == 2250
    assert risk["scenario"]["value_after_shock_usd"] == 1575
    assert risk["source"]["kind"] == "fixture"
    yield_result = results["assess_defi_yield"]
    assert isinstance(yield_result, dict) and yield_result["net_yield_usd"] == 40
    plan = results["plan_zerion_action"]
    assert isinstance(plan, dict)
    assert plan["provider"] == "zerion" and plan["execution_available"] is False
    for name in ("get_zerion_preparation", "prepare_zerion_transaction"):
        preparation = results[name]
        assert isinstance(preparation, dict) and preparation["status"] == "disabled"
    results["evidence_boundary"] = "Real stdio; fixture data; no paid provider or host UI test."
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(verify())
    rendered = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(rendered)
        print(f"MCP verification passed: 14 tools, 7 calls and rejected boolean; {args.output}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
