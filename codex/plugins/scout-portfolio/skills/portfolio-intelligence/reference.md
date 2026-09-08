# Tool reference

The optional MCP server exposes eight tools:

| Tool | Purpose | Side effect |
|:--|:--|:--|
| `get_portfolio_snapshot` | Read holdings and transactions | x402 mode can pay data fees |
| `get_pnl` | Calculate explainable USD PnL | x402 mode can pay data fees |
| `parse_dca_request` | Extract explicit DCA fields | None |
| `preview_dca` | Build an approval-required proposal | None |
| `analyze_asset` | Calculate heuristic indicators | x402 mode can pay data fees |
| `dca_windows` | Classify the current DCA window | x402 mode can pay data fees |
| `set_alert` | Store an alert rule | Writes `.scout/alerts.json` |
| `check_alerts` | Evaluate saved rules | x402 mode can pay data fees |

The fixture path comes from `ZPM_FIXTURE_PATH`. Claude Code defaults it to `${CLAUDE_PLUGIN_ROOT}/fixtures/portfolio.json`.

API-key Zerion needs `ZERION_API_KEY` and `ZERION_WALLET_ADDRESS`. x402 needs `ZERION_X402_PRIVATE_KEY`, `ZERION_WALLET_ADDRESS`, and the optional dependency group. Authorization modes are exclusive. Incomplete configuration stops startup.

Zerion snapshots report per-asset positions and mapped transactions with `source.kind = "zerion_api"`. API failure returns `status: "error"` and `fallback: "none"`. Name the source when reporting results.

x402 uses a separate payment wallet. It has a per-payment cap and no cumulative budget. Repository operators should read `docs/X402.md` before enabling it.
