# Start here

Scout 0.4.0 supports Claude Code, Codex skills, local Python, and stdio MCP clients. The synthetic fixture is the default source.

After setup, ask:

> Show me what I own and what it did.

A working install returns a portfolio and PnL with the data source named.

## Install scope

Installation copies local files, registers skills or a plugin, and can start the fixture-backed MCP process. Live Zerion access begins only when the operator supplies a complete API-key or x402 configuration.

Scout has no observed-wallet signer or trade execution rail. x402 mode gives a separate payment wallet authority to pay API fees. `set_alert` writes local `.scout/alerts.json`; the package creates no daemon or scheduled task.

## Route 1: Claude Code plugin

Install [`uv`](https://docs.astral.sh/uv/), then run:

```bash
claude plugin marketplace add /absolute/path/to/scout-onchain
claude plugin install scout-portfolio@scout-portfolio-manager
```

Restart Claude Code. The root [`.mcp.json`](.mcp.json) starts `zpm-mcp` through `uv` and uses `fixtures/portfolio.json`.

Try:

```text
/portfolio-intelligence Show me what I own and what it did
/portfolio-intelligence What is my PnL?
/portfolio-intelligence Preview a weekly $300 ETH DCA request
```

## Route 2: Codex skills and MCP

The generated Codex plugin contains skills and metadata:

```bash
codex plugin marketplace add /absolute/path/to/scout-onchain/codex/.agents/plugins
codex plugin add scout-portfolio --marketplace scout-portfolio-manager
codex plugin list
```

Attach the executable tools as a separate stdio server. Replace both paths:

```bash
codex mcp add scout-portfolio \
  --env ZPM_FIXTURE_PATH=/absolute/path/to/scout-onchain/fixtures/portfolio.json \
  -- uv run --project /absolute/path/to/scout-onchain --extra mcp zpm-mcp
```

Restart Codex and confirm the `scout-portfolio` tools appear. [`scripts/build_host_layouts.py`](scripts/build_host_layouts.py) regenerates the skills copy. It does not copy the Python runtime into the generated plugin directory.

## Route 3: Python

Python 3.11 or newer is required.

```bash
uv sync --extra test --extra mcp
uv run pytest -q
```

Without `uv`:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e '.[test,mcp]'
.venv/bin/pytest -q
```

Call the host directly:

```bash
uv run python - <<'PY'
from scout_portfolio_manager.host import ReadOnlyHost

host = ReadOnlyHost("fixtures/portfolio.json")
print(host.get_pnl())
PY
```

Run the MCP server with `uv run --extra mcp zpm-mcp`.

## Route 4: Cursor or another stdio MCP client

Merge this entry into the client's MCP configuration. Replace the absolute paths.

```json
{
  "mcpServers": {
    "scout-portfolio": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/absolute/path/to/scout-onchain",
        "--extra",
        "mcp",
        "zpm-mcp"
      ],
      "env": {
        "ZPM_FIXTURE_PATH": "/absolute/path/to/scout-onchain/fixtures/portfolio.json"
      }
    }
  }
}
```

Restart the client and inspect its MCP tool list. Host activation remains unverified until this check succeeds on that host.

## Optional Zerion data

API-key mode needs `ZERION_API_KEY` and `ZERION_WALLET_ADDRESS`. x402 mode needs `ZERION_X402_PRIVATE_KEY`, `ZERION_WALLET_ADDRESS`, and the `x402` dependency extra. The modes are exclusive. See [`docs/X402.md`](docs/X402.md) before enabling payments.

The live source reads positions and mapped transactions. Call-time failure returns a typed error with `fallback: "none"`.

## Browser demo

```bash
uv run --project . demo/zerion-portfolio-agent/server.py
```

Open `http://127.0.0.1:8787`. The demo reads the fixture and ignores Zerion environment variables.

## Runtime boundary

The eight tools cover portfolio observation, PnL, DCA parsing and preview, asset analysis, DCA windows, and local alerts. Complete previews keep `approval_state=required` and `execution_available=false`. Approval identity, trade execution, settlement verification, live price history, and pushed alerts are outside version 0.4.0.

Keep secrets and personal wallet data out of source, fixtures, prompts, logs, and issue reports. Read [`SECURITY.md`](SECURITY.md), [`DATA-AND-PRIVACY.md`](DATA-AND-PRIVACY.md), and [`SUPPORT.md`](SUPPORT.md) before using live data.
