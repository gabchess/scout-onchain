# Tool reference

| Tool | Purpose | Side effect |
|:--|:--|:--|
| `get_portfolio_snapshot` | Read holdings and transactions | x402 mode can pay analytics fees |
| `get_pnl` | Calculate explainable USD PnL | x402 mode can pay analytics fees |
| `parse_dca_request` | Extract explicit DCA fields | None |
| `preview_dca` | Build an approval-required proposal | None |
| `analyze_asset` | Calculate heuristic indicators | x402 mode can pay analytics fees |
| `dca_windows` | Classify the current DCA window | x402 mode can pay analytics fees |
| `set_alert` | Store an alert rule | Writes `.scout/alerts.json` |
| `check_alerts` | Evaluate saved rules | x402 mode can pay analytics fees when rules exist |

The fixture path comes from `ZPM_FIXTURE_PATH`. Claude Code defaults it to `${CLAUDE_PLUGIN_ROOT}/fixtures/portfolio.json`.

API-key Zerion needs `ZERION_API_KEY` and `ZERION_WALLET_ADDRESS`. x402 needs `ZERION_X402_PRIVATE_KEY`, `ZERION_WALLET_ADDRESS`, and the optional dependency group. Authorization modes are exclusive. Incomplete configuration stops startup.

Zerion snapshots contain per-asset positions and mapped transactions with `source.kind = "zerion_api"`. An API failure returns `status: "error"` and `fallback: "none"`.

x402 uses a separate Base payment wallet for analytics. The defaults are `$0.05` per payment and `$1.05` per process. Scout reserves budget before every SDK payment payload, including recovery. Read `docs/X402.md` before enabling it.

`preview_dca` accepts optional quote output, fee, slippage, expiry, and max-fee values supplied by the caller. Missing values become labeled fixture assumptions. Optional Zerion CLI preparation is described in `docs/ZERION-PREPARATION.md`; Scout cannot execute the resulting proposal.
