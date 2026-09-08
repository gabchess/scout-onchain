# Claim status

Source: `gabchess/scout-onchain` 0.4.0. Update this table when behavior or evidence changes.

| Claim | Status | Evidence and limit |
|:--|:--|:--|
| Reads Zerion holdings and transaction history | TESTED OFFLINE | Injected-response tests cover mapped positions and transaction `links.next`. |
| Calculates portfolio PnL | VERIFIED WITH FIXTURE | `get_pnl` uses observed buys for cost basis and leaves missing basis unknown. |
| Analyzes markets and DCA windows | FIXTURE ONLY | `analyze_asset` and `dca_windows` use synthetic price history with fixed low confidence. |
| Sends alerts to channels | ROADMAP | `set_alert` writes a local file that `check_alerts` evaluates on demand. |
| Connects an observed wallet | OUT OF SCOPE | Zerion receives an address without a WalletConnect flow or observed-wallet signer. |
| Uses x402 for paid Zerion reads | IMPLEMENTED, LIVE UNVERIFIED | Offline SDK construction confirms wiring without proving paid live behavior; the payment wallet can sign and spend USDC. |
| Caps x402 spend | PER PAYMENT ONLY | The default is `$0.05`, with no cumulative budget and up to 21 top-level requests per snapshot at the default page limit. |
| Creates automated buys | ROADMAP | Public host surfaces stop at preview while the fake execution adapter remains test scaffolding. |
| Records approval | UNAVAILABLE | `approval_state=required` is a preview label without an approver identity or registry. |
| Runs through MCP | PARTIAL BY HOST | Claude Code uses the root MCP config, Codex attaches stdio beside generated skills, and generic clients run `zpm-mcp`. |
| Ships under MIT | VERIFIED IN TREE | See [`LICENSE.md`](LICENSE.md) and [`LICENSE-STATUS.md`](LICENSE-STATUS.md). |

The runtime stages are observe, calculate, propose, and preview. Execution and settlement verification are outside the public tool surface.
