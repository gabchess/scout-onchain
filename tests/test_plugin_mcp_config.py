"""Pin the Claude Code plugin's MCP launch contract (ADR 0004 D-2, D-7)."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _server() -> dict:
    return json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]["scout-portfolio"]


def test_plugin_launches_the_named_console_script_from_the_lockfile():
    server = _server()
    assert server["command"] == "uv"
    assert server["args"] == [
        "run",
        "--frozen",
        "--project",
        "${CLAUDE_PLUGIN_ROOT}",
        "scout-portfolio-manager",
    ]


def test_plugin_forwards_only_api_key_mode_variables_with_empty_defaults():
    # `${VAR}` with VAR unset reaches the child as the literal "${VAR}" in Claude Code
    # 2.1.273; `${VAR:-}` expands to "" and the empty value selects the fixture.
    assert _server()["env"] == {
        "ZERION_API_KEY": "${ZERION_API_KEY:-}",
        "ZERION_WALLET_ADDRESS": "${ZERION_WALLET_ADDRESS:-}",
    }


def test_plugin_never_enables_paid_or_egress_features():
    raw = (ROOT / ".mcp.json").read_text()
    for name in ("X402", "SCOUT_ENABLE", "TYPESAFE", "SCOUT_DOTENV", "ZPM_FIXTURE_PATH"):
        assert name not in raw
