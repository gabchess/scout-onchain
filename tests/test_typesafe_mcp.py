"""MCP-layer check for D-9.5: both DCA tools return needs_confirmation over real stdio."""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

STUB_DIR = Path(__file__).resolve().parent / "typesafe_stub"
TEXT = "$200 budget, put $50 weekly into ETH on base from wallet:a to rail:b"


async def _call(env):
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "scout_portfolio_manager.mcp_server"], env=env
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            out = {}
            for name in ("parse_dca_request", "preview_dca"):
                response = await session.call_tool(name, {"text": TEXT})
                assert not response.isError, response
                out[name] = json.loads(response.content[0].text)
            return out


def test_stdio_tools_return_needs_confirmation_with_stubbed_transport(tmp_path):
    dotenv = tmp_path / "scout.env"
    dotenv.write_text("TYPESAFE_API_KEY" + "=stub-value\n")
    dotenv.chmod(0o600)
    env = {
        "PATH": os.environ.get("PATH", os.defpath),
        "HOME": str(tmp_path),
        "PYTHONPATH": os.pathsep.join([str(STUB_DIR), os.environ.get("PYTHONPATH", "")]),
        "SCOUT_TEST_TYPESAFE_STUB": "1",
        "SCOUT_TYPESAFE": "1",
        "SCOUT_DOTENV": str(dotenv),
        # Belt and braces: if the stub failed to load, a real request dies at a dead proxy.
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "https_proxy": "http://127.0.0.1:9",
    }
    results = asyncio.run(asyncio.wait_for(_call(env), 60))
    for result in results.values():
        assert result["status"] == "needs_confirmation"
        assert result["field_sources"]["amount_usd"] == "model_selected"
        assert result["intent"]["amount_usd"] == 50.0
    assert results["preview_dca"]["preview"] is None
