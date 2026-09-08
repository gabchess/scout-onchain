# Support

This is an early, community-oriented repository rather than a hosted service. No production support SLA or guaranteed response time is provided.

## Stop-and-preserve-the-error rule

Before changing anything, preserve the complete error text, the command that produced it, the package version (`python -c "import scout_portfolio_manager; print(scout_portfolio_manager.__version__)"` if available, or the installed plugin/pyproject version), and whether the default fixture or the live Zerion adapter was in use. Do not delete the fixture, reinstall the package, or reset the host as a first diagnostic step; each of those can destroy the evidence needed to tell a real regression from a local misconfiguration.

## Named regressions by version

### 0.1.0: bare `zpm-mcp` command fails with `ENOENT`

`.mcp.json` launched a bare `zpm-mcp` command. Unless the repository's `.venv/bin` happened to already be on the launching shell's PATH, Claude Code failed to start the MCP server with `ENOENT`.

**Fixed in 0.2.0.** `.mcp.json` now runs `uv run --project ${CLAUDE_PLUGIN_ROOT:-.} --extra mcp zpm-mcp`, which resolves the project and its `mcp` extra through `uv` alone.

**Recovery:** upgrade to 0.2.0 or later. If you must stay on 0.1.0, ensure `uv` and the repository's `.venv/bin` are both on the PATH of the shell Claude Code launches from, or run the server manually:

```bash
.venv/bin/pip install -e '.[mcp]'
.venv/bin/zpm-mcp
```

### 0.1.0: Zerion adapter exposed only an aggregate holding, no transaction ledger

The 0.1.0 release's optional Zerion source returned a single synthetic aggregate holding, not real per-asset positions or a transaction history, and could not compute basis from observed transactions.

**Fixed in 0.2.0.** The adapter now reads `GET /wallets/{addr}/positions/` and a mapped transaction ledger from `GET /wallets/{addr}/transactions/`, and `get_pnl` computes basis from each asset's observed buy transactions.

**Recovery:** upgrade to 0.2.0 or later. There is no in-place migration; the 0.1.0 aggregate-only adapter is superseded, not configurable.

## Current caveats

The parser accepts both a bare numeric `quantity` and Zerion's `{"float": ...}` object. Prior development inspection confirmed the object form. Current live compatibility remains outside CI. Preserve a secret-scrubbed response shape if mapping fails.

x402 has a per-payment cap and no cumulative budget in 0.4.0. The `watch` report blocks x402 because it repeats snapshot reads. Paid integration status remains live unverified; see [`docs/X402.md`](docs/X402.md).

## Before opening an issue

- Reproduce with the default synthetic fixture where possible.
- Include the command, Python version, package version, and a minimal, complete error message.
- Remove API keys, private keys, seed phrases, wallet addresses, and other personal data.
- For API-backed behavior, note the authorization mode and configured Zerion endpoint access.

## Questions and bugs

Open a GitHub issue for reproducible bugs or documentation corrections. Use a private security channel for vulnerabilities; see [`SECURITY.md`](SECURITY.md). Feature requests should describe the user-facing behavior and its safety boundary.
