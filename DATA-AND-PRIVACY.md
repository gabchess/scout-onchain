# Data and privacy

## Default behavior

The default configuration reads the synthetic JSON fixture at `fixtures/portfolio.json`. The local host and MCP server do not persist user data. They do not call Zerion or an execution provider unless an operator separately configures the optional API adapter.

`fixtures/price_history.json`, read by `analyze_asset` and `dca_windows`, is synthetic, the same status as `fixtures/portfolio.json`. `.scout/alerts.json`, written by `set_alert` and read by `check_alerts`, is local-only, never transmitted, and contains no secrets, only the asset, kind, and threshold values a user chose.

## Optional Zerion adapter

`ZerionAPIReader` makes a read-only request for one wallet's positions and transactions when explicitly configured. The adapter receives the wallet address and API credential supplied by its host, and returns real per-asset holdings and a mapped transaction ledger. It does not sign, submit, or execute transactions.

The host and MCP server enable this source only when `ZERION_API_KEY` and `ZERION_WALLET_ADDRESS` are both present in the server process environment. The key is read once at startup, held in memory for the process lifetime, and excluded from object representations, error messages, tool results, and logs written by this package. A partial configuration stops the server instead of silently serving the fixture. The wallet address is sent to Zerion in the request path and is returned in snapshot results, so treat results as containing personal wallet data.

In x402 mode (`ZERION_X402_PRIVATE_KEY` + `ZERION_WALLET_ADDRESS`), the same read-only requests are authorized per call by a small USDC payment on Base instead of an API key. The payment wallet's private key is read once at startup, held in memory, and excluded from representations, errors, results, and logs. Per-call spend is capped client-side (default `$0.05`) before any payment is signed. The payment itself is public onchain data: the payment wallet address and per-call fees are visible on Base, so use a dedicated wallet that does not link to identities the operator wants kept private. The observed wallet never signs anything.

The host application is responsible for credential storage, network logs, retention, access control, and deletion. Use a customer-controlled secret manager. Do not place credentials or personal wallet data in source files, fixtures, prompts, logs, or support reports.

API-backed data may be incomplete, stale, unavailable, or subject to the permissions and limits of the configured Zerion account. Review the applicable Zerion terms and privacy documentation before using real wallet data.

## Retention

This repository itself has no database or hosted retention service. Any data retained by an integrating application, MCP client, proxy, operating-system logs, or API provider is outside this repository's control and must be assessed by that operator.
