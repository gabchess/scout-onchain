# Unsigned Zerion preparation

Scout exposes 14 MCP tools. `prepare_zerion_transaction` and `get_zerion_preparation` add optional unsigned EVM preparation. Both are disabled by default. They cannot sign, submit or settle a transaction.

## Enable explicitly

Install and verify the official `zerion-cli` version 1.9.1 separately. Scout checks package metadata and executable location; this is a compatibility check, not cryptographic verification of the installed package. The inspected upstream source was [zeriontech/zerion-ai at 7a873d1](https://github.com/zeriontech/zerion-ai/tree/7a873d1c91d4cdfb24bbe79fd8cfabb72544bb6a).

Set these in your MCP host's private environment configuration:

| Variable | Value |
|---|---|
| `ZPM_ZERION_PREPARE_ENABLED` | `1` |
| `ZPM_ZERION_CLI_PATH` | Absolute path to the verified package's `cli/zerion.js` |
| `ZPM_ZERION_PREPARE_STORE` | Absolute SQLite file path in a private operator directory |
| `ZPM_ZERION_PREPARE_API_KEY` | Zerion API key supplied through the host's secret mechanism |

This configuration is independent of portfolio analytics mode. Do not put keys in a repository, prompt, transcript or command argument. The child receives only PATH, the existing HOME, LANG and the dedicated API key. Wallet private keys, agent tokens and arbitrary environment overrides are excluded. The CLI still reads the operator's existing Zerion configuration and can perform its own legacy configuration migration on startup. Use a dedicated OS account or container for isolation.

Preparation calls the installed executable with a fixed argument list and `--prepare --review`. No shell is invoked. Zerion quote/build services and the CLI's configured chain RPC providers may receive wallet addresses and transaction intent. Network endpoints follow the operator's Zerion configuration. Scout adds no telemetry. The CLI must already be trusted and installed; Scout downloads no executable.

## Supported intent

Use `swap`, `transfer` or `bridge`. Chains are ethereum, base, arbitrum, optimism, polygon and avalanche. Supply an exact source wallet, token contract addresses (or `native`), a positive decimal amount string, and a unique request ID. Transfers require a destination. Bridges require both the destination chain and wallet. Slippage uses basis points with a maximum of 500. Solana preparation is unsupported in this version.

Example tool arguments, using illustrative addresses:

```json
{"request_id":"review-001","action":"transfer","chain":"base","source_wallet":"0x1111111111111111111111111111111111111111","asset":"native","amount":"0.001","destination":"0x2222222222222222222222222222222222222222"}
```

## Evidence and recovery

A request is reserved in SQLite before the provider call. The same ID and intent reuse the stored result; changed intent is rejected. A prepared envelope expires after 120 seconds. Expiry, timeout, an interrupted process or invalid provider response never cause an automatic retry. `get_zerion_preparation` reads local state only. It cannot reconcile an onchain transaction.

The response reports `executed=false`, `execution_available=false` and `settlement=not_attempted`. It exposes an envelope digest and intent summary. Unsigned payloads remain in the local database, which is created with mode 0600. Use one private store per operator. The store has a 5,000-request limit; archive it through an operator-controlled maintenance process when full.

Validation checks envelope version, chain, source address, declared input asset and amount, expiry, transaction shape and declared transfer/bridge destination. It does not decode router calldata, verify output amounts or prove that transaction semantics match the request. `transaction_semantics_verified=false` remains explicit. A future signing flow needs separate semantic validation and fresh user authorization.

Tests use a fake CLI and fixture envelopes. No live Zerion preparation, signing, broadcast, paid request or settlement has been verified by this change. Existing x402 access pays only for Zerion analytics and remains separate from transaction preparation.
