# zerion-adapter data and privacy

## Default state

The adapter is disabled by default. With no complete API-key or x402 configuration, it makes no request.

## When enabled

When enabled, the adapter reads one wallet's positions and transaction history. It:

- reads the selected credential and wallet address at startup, holds the credential in memory, and excludes its value from package errors, results, representations, and log lines;
- returns per-asset holdings and a mapped transaction ledger; the wallet address itself is sent to Zerion in the request path and appears in the returned snapshot, so treat results as containing personal wallet data;
- stops the host process on a partial credential pair (one variable set, not both) rather than silently falling back to the fixture;
- has no observed-wallet signing or trade path. x402 mode signs and pays data fees from a separate wallet, with a per-payment cap and no cumulative budget.

## What this component does not control

Zerion's own logging, retention, and data handling for the request path are outside this repository's control; see Zerion's published terms and privacy documentation, referenced in [`TERMS-OF-USE.md`](TERMS-OF-USE.md), for that boundary. Credential storage, host-level network logs, and access control are the operator's responsibility; see [`SECURITY.md`](../../SECURITY.md).
