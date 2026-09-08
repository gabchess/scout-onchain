# AGENTS.md

Give an agent this repository folder or ZIP. Install Scout. Do not invent capabilities from marketing copy. Read [`CLAIMS.md`](CLAIMS.md) before repeating product claims.

## Install routes

1. Claude Code: [`START-HERE.md`](START-HERE.md) Route 1 (`scout-portfolio@scout-portfolio-manager`).
2. Codex: install Route 2 skills and attach the Route 2 stdio MCP command for tools.
3. Plain Python: Route 3 (`uv sync` / venv). Package version **0.4.0**.
4. Cursor or any MCP client: merge [`.mcp.json`](.mcp.json) into the host MCP config (or copy to `.cursor/mcp.json`). Needs `uv` on PATH. Starts `zpm-mcp` over stdio.

Discovery is not a successful install. Ask the host to list MCP tools or run `/portfolio-intelligence What is my PnL?`.

## Do

- Use the fixture by default.
- Treat Zerion as optional portfolio observation. API-key mode needs `ZERION_API_KEY` and `ZERION_WALLET_ADDRESS`. x402 mode uses a dedicated payment wallet and can spend USDC per payment.
- Keep DCA incomplete fields as clarification, never guessed.

## Do not

- Call live Zerion until the operator supplies one complete authorization mode.
- Claim channel push alerts, WalletConnect, or automated buys.
- Call execute, sign, or submit. Those tools are not available.
- Paste secrets into the repo, prompts, fixtures, or logs.

## Honesty

See [`CLAIMS.md`](CLAIMS.md), [`SECURITY.md`](SECURITY.md), [`DATA-AND-PRIVACY.md`](DATA-AND-PRIVACY.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
