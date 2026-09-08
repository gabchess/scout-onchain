# Start here

Version **0.3.3**.

Give this repository folder or ZIP to your agent and ask it to install Scout from [`START-HERE.md`](START-HERE.md). Discovery is not the same as a successful install: verify tools appear before trusting the host.

Scout is a read-only portfolio intelligence package: fixture-backed by default, with an optional read-only Zerion API adapter. This file is the exact install route for the harness you are on. Pick one.

## The first ask

After any route below, the first thing to say to Scout is:

> **"Show me what I own and what it did."**

That one sentence exercises the core chain: `get_portfolio_snapshot` (observe) then `get_pnl` (calculate), against the fixture unless you configured Zerion. If the host answers with numbers and names its data source, the install worked.

## What installing this package does and does not authorize

Installing Scout, by any route below, authorizes only local package installation: copying files, registering a plugin or skill with the host, and running the fixture-backed Python code.

It does **not** authorize:

- a live Zerion API key, a wallet connection, or any network call. The default source is the synthetic fixture at `fixtures/portfolio.json`; the optional Zerion adapter activates only when an operator explicitly sets both `ZERION_API_KEY` and `ZERION_WALLET_ADDRESS` (see [`DATA-AND-PRIVACY.md`](DATA-AND-PRIVACY.md));
- signing, submitting, or executing any transaction. No component in this package has an execute, sign, or submit code path;
- a background service, a scheduled task, or persistent state. Nothing in this package runs unless a host explicitly invokes its tools or a caller runs its server process.

## Route 1: Claude Code plugin (local marketplace)

From a terminal, with the Claude Code CLI installed:

```bash
claude plugin marketplace add /path/to/scout-portfolio-manager
claude plugin install scout-portfolio@scout-portfolio-manager
```

`marketplace.json`, not `plugin.json`, is the catalog `claude plugin marketplace add` reads; the repository ships both so installation by name works. The exact CLI spelling can vary by Claude Code release. Inside an already-running Claude Code session, the equivalent slash-command form also works:

```text
/plugin marketplace add /path/to/scout-portfolio-manager
/plugin install scout-portfolio@scout-portfolio-manager
```

Then try the first ask:

```text
/portfolio-intelligence Show me what I own and what it did
/portfolio-intelligence What is my PnL?
/portfolio-intelligence Preview a DCA request for $300 of ETH every week
```

Claude Code launches the bundled MCP server itself, through `.mcp.json`, which runs `uv run --project ${CLAUDE_PLUGIN_ROOT:-.} --extra mcp zpm-mcp`. This needs `uv` on the launching shell's PATH; no separate `pip install` or PATH setup for the package itself is required for this route.

## Route 2: Codex (Agent Skills layout)

The repository also ships a Codex-compatible plugin layout under `codex/`, generated from the same canonical source as the Claude Code plugin.

```bash
codex plugin marketplace add /path/to/scout-portfolio-manager/codex/.agents/plugins
codex plugin add scout-portfolio --marketplace scout-portfolio-manager
codex plugin list
```

Use the path syntax your operating system and shell expect. The exact CLI flags can vary by Codex release; if a command above fails, run `codex plugin --help` and adjust the verb, not the marketplace path. Restart the host and open a new session after changing plugin state.

## Route 3: Plain Python (no plugin host)

```bash
uv sync --extra test --extra mcp
uv run pytest -q
```

Or without `uv`:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e '.[test,mcp]'
.venv/bin/pytest -q
```

Python 3.11 or newer is required. Try the fixture-backed host directly:

```bash
uv run python - <<'PY'
from scout_portfolio_manager.host import ReadOnlyHost

host = ReadOnlyHost("fixtures/portfolio.json")
print(host.get_pnl())
print(host.parse_dca_request("DCA another $300 of ETH"))
PY
```

The default fixture is synthetic. It is the default data source, not live portfolio data.

To run the optional MCP server directly, without a plugin host:

```bash
uv run --extra mcp zpm-mcp
```

The server registers eight tools: `get_portfolio_snapshot`, `get_pnl`, `parse_dca_request`, `preview_dca`, `analyze_asset`, `dca_windows`, `set_alert`, and `check_alerts`. Set `ZPM_FIXTURE_PATH` to point at another local fixture.

## Route 4: Cursor or any MCP client (stdio)

Scout speaks stdio MCP. Any MCP-capable host can attach it, including Cursor, without a Scout marketplace listing.

1. Install [`uv`](https://docs.astral.sh/uv/) so it is on PATH.
2. Clone or unzip this repository.
3. Merge this repo's [`.mcp.json`](.mcp.json) into the host MCP config, or copy it to `.cursor/mcp.json` in a Cursor project:

```json
{
  "mcpServers": {
    "scout-portfolio": {
      "command": "uv",
      "args": ["run", "--project", "${CLAUDE_PLUGIN_ROOT:-.}", "--extra", "mcp", "zpm-mcp"],
      "env": {
        "ZPM_FIXTURE_PATH": "${CLAUDE_PLUGIN_ROOT:-.}/fixtures/portfolio.json"
      }
    }
  }
}
```

For Cursor outside a Claude plugin root, set `--project` to the absolute path of this checkout (or `.` when the working directory is the checkout) and point `ZPM_FIXTURE_PATH` at `fixtures/portfolio.json` under that checkout.

4. Restart the host. Confirm the `scout-portfolio` server lists tools: `get_portfolio_snapshot`, `get_pnl`, `parse_dca_request`, `preview_dca`, `analyze_asset`, `dca_windows`, `set_alert`, `check_alerts`.

Default data is the fixture. Cursor.app smoke-test may still be pending on some machines. Stdio config is the supported Cursor path today.

## Try the browser demo (any route)

```bash
uv run --project . demo/zerion-portfolio-agent/server.py
```

Then open `http://127.0.0.1:8787`. The demo runs entirely offline on the fixture; it never reads `ZERION_API_KEY`. See [`demo/zerion-portfolio-agent/README.md`](demo/zerion-portfolio-agent/README.md).

## Boundaries

Live stages are observe, calculate, propose, and preview (`approval_state=required`, host-minted `preview_id`). Execute and verify are not product tools. DCA previews require amount, asset, chain, schedule, source, and destination. Missing fields are clarified, never guessed. A complete preview is `approval_state=required` and `execution_available=false`; wallet handoff and execution are a future product direction, not a current capability.

Never add API keys, private keys, seed phrases, or wallet secrets to this repository, prompts, fixtures, or logs. For the full data and security boundary, read [`DATA-AND-PRIVACY.md`](DATA-AND-PRIVACY.md) and [`SECURITY.md`](SECURITY.md). If installation or discovery fails, continue with [`SUPPORT.md`](SUPPORT.md).
