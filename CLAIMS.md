# Claim status

Source: `gabchess/scout-onchain` 0.5.0. Each status names the strongest evidence in this repository.

| Claim | Status | Evidence and limit |
|:--|:--|:--|
| Reads Zerion holdings and transaction history | TESTED OFFLINE | Injected-response tests cover positions and paginated transactions. No current live API-key call is recorded. |
| Calculates portfolio PnL | VERIFIED WITH FIXTURE | `get_pnl` uses observed buys for cost basis and leaves missing basis unknown. |
| Offers several agent routes | VERIFIED IN PACKAGE | The host and MCP registry expose portfolio, PnL, DCA proposal, analysis, DCA-window, and local-alert tools. |
| Builds DCA proposals | VERIFIED WITH FIXTURE | Complete previews require approval and expose no execution action. Optional quote fields come from the caller. |
| Analyzes markets and DCA windows | FIXTURE ONLY | These tools use bundled synthetic price history with fixed low confidence. |
| Checks alerts | LOCAL ON DEMAND | `set_alert` writes `.scout/alerts.json`; `check_alerts` evaluates rules when called. No channel delivery is present. |
| Uses x402 for paid Zerion reads | IMPLEMENTED, LIVE UNVERIFIED | The real SDK session builds offline. The payment wallet can sign and spend USDC. No paid live request is recorded. |
| Caps x402 spend | TESTED OFFLINE | The defaults are `$0.05` per payment and `$1.05` per process. Scout reserves before every SDK payment payload, including recovery. |
| Signs with the observed wallet | ABSENT | The observed wallet is an address input. The only signer is the separate x402 payment wallet when configured. |
| Executes trades | ABSENT | Public tools stop at proposal preview or optional unsigned EVM preparation. No signing, broadcast or settlement tool ships. |
| Runs through MCP | TESTED LOCALLY | The registry is pinned to the public tool set. Host-specific activation still needs inspection after installation. |
| Ships under MIT | VERIFIED IN TREE | See [`LICENSE.md`](LICENSE.md) and [`LICENSE-STATUS.md`](LICENSE-STATUS.md). |

## Unreleased knowledge proposal

The working proposal adds source-linked knowledge retrieval, gross portfolio concentration and shock calculations, assumed yield scenarios, and a Zerion-only action planner. These additions are tested offline. The glossary includes 1,059 community entries whose individual definitions remain unverified; the 48 original cards also need task-level host evaluation. No model-performance improvement or complete DeFi risk coverage is claimed.

Portfolio actions remain unavailable. The official Zerion AI CLI provides capabilities outside Scout, including signing and trading. This proposal does not call them. Host-global behavior across other installed plugins is outside Scout's tool boundary.

See [knowledge proposal](docs/knowledge/README.md) for formulas, inputs, source maintenance and limits.

Scout's public stages are observe, calculate, propose, and preview. Payment for data access belongs to the x402 source boundary.

Unsigned Zerion preparation is implemented and fixture-tested. Live provider compatibility and transaction semantics remain unverified. See [the preparation contract](docs/ZERION-PREPARATION.md).
