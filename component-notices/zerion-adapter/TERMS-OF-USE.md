# zerion-adapter terms of use

## What this component is

`ZerionAPIReader` and `ZerionWalletReader` read Zerion's hosted positions and transactions endpoints at `https://api.zerion.io`. The source is disabled by default. API-key mode uses `ZERION_API_KEY`; x402 mode uses a payment-wallet key through `x402_source.py`. The x402 wallet can sign and pay data fees. Neither mode can sign for the observed wallet or execute a trade.

## Governing terms

This project's MIT license covers the adapter's own source code. It does not cover, extend, or modify Zerion's API terms. Any use of the live API, meaning any run with real credentials against `api.zerion.io`, is governed entirely by Zerion's own terms, published at https://zerion.io/terms, and by the scope, rate limits, and authorization of the operator's own Zerion account. Review Zerion's current terms directly before enabling this adapter with real credentials; this project does not restate, summarize, or interpret them, and Zerion's terms may change independently of this repository.

## Operator responsibility

The operator supplies and controls each credential through a secret manager, per [`SECURITY.md`](../../SECURITY.md) and [`DATA-AND-PRIVACY.md`](DATA-AND-PRIVACY.md). Zerion and x402 services receive data required by their protocols.
