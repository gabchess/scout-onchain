# Data and privacy

## Default behavior

The default configuration reads the synthetic JSON fixture at `fixtures/portfolio.json`. The local host and MCP server do not call Zerion until an operator configures the optional source. No execution provider is wired into the product.

`fixtures/price_history.json`, read by `analyze_asset` and `dca_windows`, is synthetic, the same status as `fixtures/portfolio.json`. `~/.scout/alerts.json` (or the file named by `ZPM_ALERTS_PATH`), written by `set_alert` and read by `check_alerts`, is local-only, never transmitted, and contains no secrets, only the asset, kind, and threshold values a user chose.

## Optional Zerion adapter

`ZerionAPIReader` makes a read-only request for one wallet's positions and transactions when explicitly configured. The adapter receives the wallet address and API credential supplied by its host, and returns real per-asset holdings and a mapped transaction ledger. It does not sign, submit, or execute transactions.

The host and MCP server enable this source only when `ZERION_API_KEY` and `ZERION_WALLET_ADDRESS` are both present in the server process environment. The key is read once at startup, held in memory for the process lifetime, and excluded from object representations, error messages, tool results, and logs written by this package. A partial configuration stops the server instead of silently serving the fixture. The wallet address is sent to Zerion in the request path and is returned in snapshot results, so treat results as containing personal wallet data.

In x402 mode (`ZERION_X402_PRIVATE_KEY` + `ZERION_WALLET_ADDRESS` + `ZERION_X402_PAY_TO`), the same reads are authorized by USDC payments on Base. `ZERION_X402_PAY_TO` pins the only address Scout will pay. The SDK session retains the payment key and signing authority in memory. Scout suppresses the key value in its errors, results, representations, and package logs. The host, SDK, and network stack remain separate logging boundaries.

Scout reserves the full payment cap before every SDK payment payload, including recovery. The defaults are `$0.05` per payment and `$1.05` for the process lifetime. Reservations remain counted after ambiguous failures. A restart creates a new budget. The payment wallet address and fees are public on Base. Use a dedicated wallet with a small balance. The observed wallet supplies an address and never signs.

The host application is responsible for credential storage, network logs, retention, access control, and deletion. Use a customer-controlled secret manager. Do not place credentials or personal wallet data in source files, fixtures, prompts, logs, or support reports.

API-backed data may be incomplete, stale, unavailable, or subject to the permissions and limits of the configured Zerion account. Review the applicable Zerion terms and privacy documentation before using real wallet data.

## Optional TypeSafe DCA intent resolution

Off by default. It runs only when the MCP server environment has both `SCOUT_TYPESAFE=1` and `SCOUT_DOTENV` set to an absolute path of a file you own that holds `TYPESAFE_API_KEY`. Scout sends a request only when a DCA text has two or more candidates for one field, or a single candidate in a negated phrase.

What leaves the machine, to `api.typesafe.ai` only:

- Short windows of the DCA text, at most 24 characters each side of each candidate, cut after redaction. Redaction replaces EVM addresses, base58 and bech32 addresses, ENS and SNS names, emails, and `wallet:` and `rail:` tokens with `[addr]`.
- The option labels Scout found (for example `ETH`, `$50`, `weekly`, `none`) and fixed question text.
- The model id `jev-1.12`.
- Your TypeSafe key in the `Authorization` header.

Never sent: the full request text, wallet addresses, holdings, balances, positions, transactions, or any other key.

As of 2026-09-16, TypeSafe publishes no data-retention or training-use policy page. Treat anything sent as retained by TypeSafe. Scout stores nothing about the call except failure counts by kind.

## Retention

Optional unsigned preparation stores request IDs, intent hashes, timestamps, intent summaries and unsigned transaction envelopes in an operator-selected SQLite file created with mode 0600. The preparation API key is not stored there. Records persist until the operator archives or removes the file, and the store stops accepting new requests at 5,000 records. Back up outstanding request state before maintenance. There is no hosted retention service. Any data retained by an integrating application, MCP client, proxy, operating-system logs, or API provider is outside this repository's control and must be assessed by that operator.

The [optional preparation adapter](docs/ZERION-PREPARATION.md) sends the source wallet and exact intent to the installed Zerion CLI, which can call its configured build/quote services and chain RPC endpoints. Its existing configuration and legacy migration behavior belong to the CLI. No live call was made during validation.
