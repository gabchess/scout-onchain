# Claim status

Source: `gabchess/scout-onchain` 0.6.1. Each status names the strongest evidence in this repository.

| Claim | Status | Evidence and limit |
|:--|:--|:--|
| Reads Zerion holdings and transaction history | TESTED OFFLINE | Injected-response tests cover positions and paginated transactions. No current live API-key call is recorded. |
| Reads Arc wallets through Zerion | TESTED OFFLINE | A Zerion-shaped Arc fixture runs through the reader, PnL, risk, report and alert paths. No live Arc call is recorded. |
| Calculates portfolio PnL | VERIFIED WITH FIXTURE | `get_pnl` uses observed buys for cost basis and leaves missing basis unknown. |
| Offers several agent routes | VERIFIED IN PACKAGE | The host and MCP registry expose portfolio, PnL, DCA proposal, analysis, DCA-window, and local-alert tools. |
| Builds DCA proposals | VERIFIED WITH FIXTURE | Complete previews require approval and expose no execution action. Optional quote fields come from the caller. |
| Analyzes markets and DCA windows | FIXTURE ONLY | These tools use bundled synthetic price history with fixed low confidence. |
| Checks alerts | LOCAL ON DEMAND | `set_alert` writes `~/.scout/alerts.json` (or `ZPM_ALERTS_PATH`); `check_alerts` evaluates rules when called. No channel delivery is present. |
| Uses x402 for paid Zerion reads | IMPLEMENTED, LIVE UNVERIFIED | The real SDK session builds offline. The payment wallet can sign and spend USDC. No paid live request is recorded. |
| Caps x402 spend | TESTED OFFLINE | The defaults are `$0.05` per payment and `$1.05` per process. Scout reserves before every SDK payment payload, including recovery. |
| Preflights x402 payment requirements | TESTED OFFLINE | Scout rejects non-Base, non-pinned-USDC, malformed or over-cap requirements before signing and rejects paid retries without `PAYMENT-SIGNATURE`. |
| Prepares unsigned transactions on Arc | TESTED OFFLINE, LIVE AVAILABILITY UNVERIFIED | Scout accepts Arc preparation for native USDC for transfer, swap and bridge; the 0x3600 token for transfers only. Zerion's live chain flags decide which actions work; Scout has not observed them. A refusal returns `chain_not_supported`. Fixture envelopes only; no live Arc preparation is recorded. |
| Signs with the observed wallet | ABSENT | The observed wallet is an address input. The only signer is the separate x402 payment wallet when configured. |
| Executes trades | ABSENT | Public tools stop at proposal preview or optional unsigned EVM preparation. No signing, broadcast or settlement tool ships. |
| Runs through MCP | TESTED LOCALLY | The registry is pinned to the public tool set. Host-specific activation still needs inspection after installation. |
| Ships under MIT | VERIFIED IN TREE | See [`LICENSE.md`](LICENSE.md) and [`LICENSE-STATUS.md`](LICENSE-STATUS.md). |

## 0.6.1 Arc preparation

Scout enforces chain id 5042, taken from Arc's docs. The Zerion CLI derives the id from Zerion's `external_id` for `arc`, which Scout has not observed; a different value makes every Arc preparation fail closed.

Only Arc mainnet (`arc`) is accepted. Native USDC and the 0x3600 token share one balance, so Scout refuses a swap between them. Arc USDC amounts allow at most 6 decimal places. Scout binds the native USDC value exactly at 18 decimals and decodes the 0x3600 transfer call. Other Arc tokens, such as EURC, are not decimal-checked.

## 0.6.0 Arc reads

Zerion's [supported blockchains page](https://developers.zerion.io/supported-blockchains) lists Arc with chain ID `arc` and token and transaction coverage. It marks DeFi and NFT coverage as absent. Scout sends no chain filter, so Arc positions and transactions arrive with the wallet's other chains. Arc pays gas in USDC, and Scout maps that fee like any other. Holdings with the same asset label, such as USDC on Arc and on Base, are merged before PnL and asset analysis.

Arc's EVM chain ID was reported as 5042. Zerion's docs do not show it and Scout does not use it. Unsigned Zerion CLI preparation on Arc is out of scope for 0.6.0.

## 0.5.0 advisory features

Version 0.5.0 adds source-linked knowledge retrieval, gross portfolio concentration and shock calculations, assumed yield scenarios, and a Zerion-only action planner. These additions are tested offline. The glossary includes 1,059 community entries whose individual definitions remain unverified; the 48 original cards cover a limited set of concepts. Complete DeFi risk coverage and broad model-performance improvement remain unestablished.

Portfolio actions remain unavailable. The official Zerion AI CLI provides capabilities outside Scout, including signing and trading. This proposal does not call them. Host-global behavior across other installed plugins is outside Scout's tool boundary.

See [knowledge proposal](docs/knowledge/README.md) for formulas, inputs, source maintenance and limits.

Scout's public stages are observe, calculate, propose, and preview. Payment for data access belongs to the x402 source boundary.

Unsigned Zerion preparation is implemented and fixture-tested. Live provider compatibility and transaction semantics remain unverified. See [the preparation contract](docs/ZERION-PREPARATION.md).

## Independent advice evaluation

After targeted corrections, the amended Scout runtime passed a separate six-case DeFi holdout, with all eight critical criteria met. The test used hypothetical fixtures and independent AI grading. The first twelve-case suite failed one critical completeness criterion; the subsequent four exposed regression cases passed. [The full reports](evals/independent-defi/README.md) preserve both results, partial omissions, exact runtime correspondence and host-context limitations.

This evidence concerns injected Scout context and fixture retrieval. Human expert approval, population accuracy, native plugin activation and live financial execution require separate evidence.
