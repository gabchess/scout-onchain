# Architecture

A read-only agent for one wallet. It watches, calculates, and proposes a DCA plan. You approve. It never signs, sends, or trades. This document describes how that boundary holds, from observation through the point where a proposal stops and waits on you.

```text
agent runtime / MCP client
  -> ReadOnlyHost (get_portfolio_snapshot | get_pnl | parse_dca_request | preview_dca
                   | analyze_asset | dca_windows | set_alert | check_alerts)
       -> observe: FixturePortfolioReader or optional ZerionAPIReader -> typed PortfolioSnapshot
       -> calculate: PnL calculator -> explainable PnlResult
       -> calculate: analyze_asset -> SMA/EMA/RSI/drawdown, heuristic disclosure
       -> propose: DCA parser -> partial DcaIntent
       -> propose: dca_windows -> current-window classification, not financial advice
       -> propose: set_alert -> stored threshold rule in .scout/alerts.json
       -> calculate: check_alerts -> evaluated rules, not financial advice
       -> preview: complete request -> approval_state=required + host-minted preview_id
       -> execution: not exposed by the host or MCP server
```

`preview_id` is host-minted identity on every complete preview envelope. It is non-authoritative: a stable, quotable id for future audit/idempotency use, never an authorization token, and must not be treated as one absent a registry (none exists yet). There is no session store and no execute rail in this package surface.

The default source is a local synthetic fixture. `zpm-mcp` wraps the same eight read-only tools over stdio MCP and selects the source from the environment: the Zerion API when `ZERION_API_KEY` and `ZERION_WALLET_ADDRESS` are both set, or its x402 pay-per-call variant when `ZERION_X402_PRIVATE_KEY` and `ZERION_WALLET_ADDRESS` are both set (one authorization mode at a time; setting both is a startup error, see `docs/X402.md`), otherwise the fixture. A partial pair is a startup error, and an API failure at call time returns a typed error rather than fixture data. In x402 mode an HTTP 402 after a payment attempt maps to a typed, non-retryable `payment` error kind. The optional API adapter is an external, read-only data boundary: its availability, authorization, freshness, and response shape depend on the configured Zerion account and endpoint contract.

The package contains a fake execution adapter for isolated domain/test behavior; it is not wired into the host or MCP server and does not move funds.

## Pagination

`ZerionAPIReader` reads two endpoints with different pagination shapes, per Zerion's own
documentation. `GET /wallets/{addr}/positions/` takes no pagination parameters and returns
every position in one call. The reader sends `filter[positions]=only_simple` on that call;
this makes explicit a filter value Zerion's API already defaults to, and is documentation of
existing server behavior, not a behavior change. `GET /wallets/{addr}/transactions/` paginates: the reader
requests `page[size]=100` and follows `links.next` until the API stops returning a next
cursor, bounded by `ZerionAPIConfig.max_pages` (default 20). Hitting the page cap while a
next cursor is still present, or receiving a malformed or repeated cursor, raises
`ZerionAPIPaginationError` rather than silently truncating the ledger. NFT list links (`ResponseManyLinks`) are `self`-only and are never followed. Do not send `filter[min_mined_at]` here (epoch-ms query vs ISO response). HTTP 429 has no `Retry-After` in the OpenAPI contract, but the reader parses one anyway when the response actually carries it (RFC 6585 defines the header for 429; undocumented is not the same as absent), and leaves `retry_after_seconds=None` otherwise. Only positions 503 documents `Retry-After` in the contract itself.

## Tool versioning

Each tool descriptor returned by `ReadOnlyHost.tool_manifest()` carries a `version` field,
set to the package version. Deprecation policy: a breaking change to a tool's input or
output schema ships under a new tool name or a new major package version, is announced in
`CHANGELOG.md` under an `Unreleased` or dated entry naming the affected tool, and the prior
schema stays callable for one minor release cycle after the announcement before removal.
This policy is the smallest reasonable default for the current single-consumer surface; it
is a proposal from this docs pass, not a policy validated against production tool
consumers.

## Execution-rail enforcement

The stage separation is enforced in code, not only documented. `ReadOnlyHost.call_tool`
raises `PermissionError` by name for `execute`, `execute_dca`, `submit`, and `sign`, so no
tool exists for a caller to invoke past preview, and `DcaPreview.approval_state` is a
pydantic `Literal`, checked at construction, not a string a caller can talk past. Known
gap: approval is a label today, not a record of who set it; that record should exist
before any real execution adapter replaces the fake one.
