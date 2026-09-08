# Release honesty: what is incomplete or can break

This file records important limits so the release is not mistaken for a production wallet or trading integration.

- The default data is synthetic and may be stale by design; it is not a live portfolio.
- The optional Zerion adapter relies on the configured endpoint, credentials, permissions, rate limits, network, and response shape. A successful request is not a guarantee of complete or current data.
- The adapter now maps real per-asset holdings and a transaction ledger from Zerion's positions and transactions endpoints, replacing the earlier single synthetic `PORTFOLIO` holding. It still does not invent an acquisition basis: an asset with no observed buy transaction reports a missing basis instead.
- Transaction pagination is bounded by `ZerionAPIConfig.max_pages` (default 20 pages of `page[size]=100`, overridable per deployment; no upper bound is enforced beyond a positive integer). A wallet with a longer history than the configured bound raises a typed pagination error rather than returning a silently truncated ledger.
- `retry_after_seconds` on rate-limit errors is exposed for callers. The API-key transport adds no retry loop. The x402 SDK performs its payment resend and can attempt recovery within one top-level request.
- Positions and transactions responses are mapped defensively: a position with no resolvable symbol, or a transaction with an unmapped operation type, an unmapped transfer direction, or a missing quantity/value, is skipped with a logged warning rather than guessed at.
- DCA parsing and previews do not submit, sign, execute, or verify settlement. A preview is not evidence that an order occurred.
- The package contains a fake execution adapter for isolated domain behavior; it is not connected to the host or MCP server and does not touch funds.
- No production deployment, uptime target, support SLA, investment advice, or Zerion endorsement is claimed.
- x402 limits each payment, with no cumulative session budget. One snapshot can make 21 top-level API requests at the default page limit. The SDK can make an extra paid recovery attempt inside one request. `watch` blocks x402 until a cumulative budget exists.
- x402 tests build the real SDK session offline. No live paid request is verified by this repository.
