# Security

## Authority boundary

The host and MCP server expose observation, calculation, parsing, proposal preview, analysis, and alert tools. They contain no observed-wallet connection or trade execution path. A DCA preview is a proposal with `approval_state=required`.

`set_alert` has a local side effect. It writes rule data to `~/.scout/alerts.json` (or `ZPM_ALERTS_PATH`). It does not schedule work or send notifications.

The Zerion source reads positions and mapped transactions for one address. Authorization has two modes:

| Mode | Secret | Authorized action |
|:--|:--|:--|
| API key | `ZERION_API_KEY` | Read Zerion endpoints |
| x402 | `ZERION_X402_PRIVATE_KEY` plus `SCOUT_ENABLE_X402=1` | Sign and pay USDC analytics fees on Base |

x402 needs the explicit `SCOUT_ENABLE_X402=1` opt-in (breaking change in 0.7.0). Without it an x402 key is ignored with a stderr notice that contains no values. The Claude Code plugin forwards only `ZERION_API_KEY` and `ZERION_WALLET_ADDRESS` and sets `SCOUT_ENABLE_X402` and `SCOUT_TYPESAFE` to empty values. Claude Code passes the launching shell's environment to plugin servers, and those explicit empty values override exported ones (verified on Claude Code 2.1.273). Any other MCP entry inherits an exported `SCOUT_ENABLE_X402=1`, so set it only on the one server entry that should pay.

The observed wallet never signs. The x402 payment wallet does. Scout reserves the full configured payment cap before each SDK payment payload. This includes recovery attempts. The defaults are `$0.05` per payment and `$1.05` across one process lifetime.

Reservations are conservative. Scout does not refund them after an ambiguous failure because a payment may have settled. A process restart creates a new budget. Use a dedicated wallet with a small balance and inspect its payment state before retrying.

Before the x402 SDK signs, Scout requires the exact Base mainnet network, the
pinned Base USDC contract, a positive atomic amount within the configured
per-payment cap, an explicit recipient, and a timeout that is positive and no
more than 600 seconds. `ZERION_X402_PAY_TO` is required and Scout pays that address or nothing; x402
refuses to start without it. After a paid
retry, the transport requires a non-empty `PAYMENT-SIGNATURE` header. These
checks do not replace facilitator verification and do not prove settlement.

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

## Optional TypeSafe DCA intent

`SCOUT_TYPESAFE=1` plus an absolute `SCOUT_DOTENV` path turns on one outbound call type to `https://api.typesafe.ai/v1/systemone`. It is off by default. The Claude Code plugin sets `SCOUT_TYPESAFE` to empty, which overrides an exported shell value. `TYPESAFE_API_KEY` is read only from that file, never from the process environment. Scout opens the file without following symlinks and refuses it unless it is a regular file owned by the current user, with no group or world permission bits, and at most 64 KiB. Only the `TYPESAFE_API_KEY` line is parsed.

The request never follows redirects, has one 3 second deadline and no retry. What leaves the machine is described in [`DATA-AND-PRIVACY.md`](DATA-AND-PRIVACY.md). A model answer can never make a DCA request `ready`: any value it picks returns `needs_confirmation`, and `preview_dca` still requires approval with no execution path.
