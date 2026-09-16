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
    # Claude Code plugin children inherit the launching shell's environment. An explicit
    # empty value overrides an inherited SCOUT_ENABLE_X402=1 or SCOUT_TYPESAFE=1
    # (probed 2026-09-16), so the plugin can never switch on paid or egress features.
    assert _server()["env"] == {
        "ZERION_API_KEY": "${ZERION_API_KEY:-}",
        "ZERION_WALLET_ADDRESS": "${ZERION_WALLET_ADDRESS:-}",
        "SCOUT_ENABLE_X402": "",
        "SCOUT_TYPESAFE": "",
    }


def test_plugin_never_forwards_payment_egress_or_fixture_variables():
    raw = (ROOT / ".mcp.json").read_text()
    for name in ("X402_", "TYPESAFE_API_KEY", "SCOUT_DOTENV", "ZPM_FIXTURE_PATH"):
        assert name not in raw


def test_plugin_opt_in_overrides_select_the_disabled_state():
    from scout_portfolio_manager import mcp_server
    from scout_portfolio_manager.portfolio import FixturePortfolioReader
    from scout_portfolio_manager.typesafe_intent import load_key

    env = {k: v for k, v in _server()["env"].items() if "${" not in v}
    inherited = {
        "SCOUT_ENABLE_X402": "1",
        "SCOUT_TYPESAFE": "1",
        "ZERION_X402_PRIVATE_KEY": "inherited-not-a-key",
        "ZERION_WALLET_ADDRESS": "0x" + "1" * 40,
        "SCOUT_DOTENV": "/tmp/inherited.env",
    }
    effective = {**inherited, **env, "ZERION_API_KEY": "", "ZERION_WALLET_ADDRESS": ""}
    assert isinstance(mcp_server.build_host(effective).reader, FixturePortfolioReader)
    assert load_key(effective) is None
