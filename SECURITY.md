# Security

## Authority boundary

The host and MCP server expose observation, calculation, parsing, proposal preview, analysis, and alert tools. They contain no observed-wallet connection or trade execution path. A DCA preview is a proposal with `approval_state=required`.

`set_alert` has a local side effect. It writes rule data to `.scout/alerts.json`. It does not schedule work or send notifications.

The Zerion source reads positions and mapped transactions for one address. Authorization has two modes:

| Mode | Secret | Authorized action |
|:--|:--|:--|
| API key | `ZERION_API_KEY` | Read Zerion endpoints |
| x402 | `ZERION_X402_PRIVATE_KEY` | Sign and pay USDC analytics fees on Base |

The observed wallet never signs. The x402 payment wallet does. Scout reserves the full configured payment cap before each SDK payment payload. This includes recovery attempts. The defaults are `$0.05` per payment and `$1.05` across one process lifetime.

Reservations are conservative. Scout does not refund them after an ambiguous failure because a payment may have settled. A process restart creates a new budget. Use a dedicated wallet with a small balance and inspect its payment state before retrying.

Asset indicators and DCA windows use synthetic price history. They are heuristic and have fixed low confidence. DCA quote fields are caller inputs or labeled fixture assumptions. The standard analytics flow does not fetch a swap quote. Optional unsigned preparation can request one through Zerion CLI.

## Secrets and data

Keep API keys, private keys, seed phrases, and wallet secrets in a host-controlled secret manager or environment. Keep them out of source, fixtures, prompts, logs, and issue reports.

The package suppresses credential values in its errors and representations. The host, operating system, network stack, x402 SDK, and API provider have their own logging and retention behavior.

Fixture data is synthetic. Real wallet addresses appear in Zerion request paths and snapshot results.

## Report a vulnerability

Use the private security channel configured by the operator or repository owner. If none exists, open a minimal issue asking for a security contact. Exclude exploit details, credentials, and personal wallet data.

This repository has no response-time or production-support promise. See [`SUPPORT.md`](SUPPORT.md).

## Optional preparation

Explicit operator configuration enables unsigned EVM preparation through Zerion CLI. The preparation and status tools create or read a local SQLite store. Preparation sends intent to the configured Zerion services and RPC providers. It has no signing or broadcast path. Provider-declared fields receive strict checks; calldata semantics remain unverified. See [configuration, retention and recovery](docs/ZERION-PREPARATION.md).
