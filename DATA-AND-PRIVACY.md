# Data and privacy

## Default behavior

The default configuration reads the synthetic JSON fixture at `fixtures/portfolio.json`. The local host and MCP server do not call Zerion until an operator configures the optional source. No execution provider is wired into the product.

`fixtures/price_history.json`, read by `analyze_asset` and `dca_windows`, is synthetic, the same status as `fixtures/portfolio.json`. `.scout/alerts.json`, written by `set_alert` and read by `check_alerts`, is local-only, never transmitted, and contains no secrets, only the asset, kind, and threshold values a user chose.

## Optional Zerion adapter

`ZerionAPIReader` makes a read-only request for one wallet's positions and transactions when explicitly configured. The adapter receives the wallet address and API credential supplied by its host, and returns real per-asset holdings and a mapped transaction ledger. It does not sign, submit, or execute transactions.

The host and MCP server enable this source only when `ZERION_API_KEY` and `ZERION_WALLET_ADDRESS` are both present in the server process environment. The key is read once at startup, held in memory for the process lifetime, and excluded from object representations, error messages, tool results, and logs written by this package. A partial configuration stops the server instead of silently serving the fixture. The wallet address is sent to Zerion in the request path and is returned in snapshot results, so treat results as containing personal wallet data.

In x402 mode (`ZERION_X402_PRIVATE_KEY` + `ZERION_WALLET_ADDRESS`), the same reads are authorized by USDC payments on Base. The SDK session retains the payment key and signing authority in memory. Scout suppresses the key value in its errors, results, representations, and package logs. The host, SDK, and network stack remain separate logging boundaries.

Scout reserves the full payment cap before every SDK payment payload, including recovery. The defaults are `$0.05` per payment and `$1.05` for the process lifetime. Reservations remain counted after ambiguous failures. A restart creates a new budget. The payment wallet address and fees are public on Base. Use a dedicated wallet with a small balance. The observed wallet supplies an address and never signs.

The host application is responsible for credential storage, network logs, retention, access control, and deletion. Use a customer-controlled secret manager. Do not place credentials or personal wallet data in source files, fixtures, prompts, logs, or support reports.

API-backed data may be incomplete, stale, unavailable, or subject to the permissions and limits of the configured Zerion account. Review the applicable Zerion terms and privacy documentation before using real wallet data.

## Retention

This repository itself has no database or hosted retention service. Any data retained by an integrating application, MCP client, proxy, operating-system logs, or API provider is outside this repository's control and must be assessed by that operator.
