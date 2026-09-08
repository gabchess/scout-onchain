# What is true today

Scout claims for LinkedIn and README. Source: HEAD `gabchess/scout-portfolio-manager` (Egdod claims map 2026-09-04). Update this table when the product changes.

| Claim | Verdict | What is true |
|:--|:--|:--|
| Zerion API: holdings and transaction history | TRUE | Optional read-only adapter. Positions one-shot. Transactions follow `links.next`. Fixture is the default. |
| Calculates PnL / answers portfolio questions | PARTIAL | `get_pnl` and read intents. Not freeform "anything you ask." |
| Market analysis and DCA entry windows | PARTIAL | `analyze_asset` and `dca_windows` are live tools. Price series is `fixtures/price_history.json` only. No live price feed. Heuristic. Not financial advice. |
| Alerts on preferred channels | FALSE / ROADMAP | `set_alert` / `check_alerts` write and evaluate local `.scout/alerts.json` on demand. No Slack, email, or Telegram push. |
| Connects to Zerion Wallet (optional) | FALSE / reframe | Optional read-only Zerion via `ZERION_API_KEY` + `ZERION_WALLET_ADDRESS`. Not WalletConnect. Not an in-app wallet connect. |
| x402 pay-per-call Zerion access (optional) | TRUE | `ZERION_X402_PRIVATE_KEY` + `ZERION_WALLET_ADDRESS`: a dedicated payment wallet pays ~$0.01 USDC on Base per read call, capped client-side (default `$0.05`) before signing. The observed wallet never signs. Still read-only. |
| Creates automated buys (optional) | ROADMAP | Host and MCP have no execute, sign, or submit tool. Fake execution adapter is test-only. |
| Architecture observe to calculate to propose to approve (six layers) | PARTIAL | Live stages: observe, calculate, propose, preview (host-minted `preview_id`). Approve is a label (`approval_state=required`). Execute and verify are not product tools. |
| TA: SMA 20, EMA 12, RSI 14, 30-day range, drawdown vs cost basis | TRUE (fixture) | `analyze_asset`. Disclose synthetic price series. |
| Any MCP-enabled agent can call Scout | PARTIAL | Claude plugin, Codex mirror, and `zpm-mcp` stdio. Cursor and Hermes use the same stdio MCP config. Cursor.app smoke-test may still be pending. |
| Open source, free | TRUE | MIT. |

## LinkedIn-safe one-liners

- Alerts: local on-demand rules in `.scout/alerts.json`. Push channels are roadmap.
- Wallet: optional read-only Zerion via API key and address. Not a wallet connect UX.
- x402: optional pay-per-call Zerion reads. A dedicated payment wallet signs per-call data fees only, capped before signing. Scout itself still executes nothing.
- Buys: roadmap. Preview only today.
- Layers: observe, calculate, propose, preview. Execute and verify are not shipped.
