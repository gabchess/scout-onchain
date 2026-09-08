# Architecture

Scout exposes one customizable host through Python and stdio MCP. The calling agent selects one tool or composes several tools from the user's request.

```text
agent or MCP client
  -> ReadOnlyHost
       -> observe: fixture or Zerion positions and transactions
       -> calculate: PnL and heuristic asset indicators
       -> propose: DCA window, DCA intent, or local alert rule
       -> preview: approval-required DCA proposal + preview_id
       -> stop: no trade execution or settlement tool
```

## Sources

The synthetic fixture is the default. The server selects one live authorization mode only when its complete environment is present:

| Mode | Required values | External effect |
|:--|:--|:--|
| API key | `ZERION_API_KEY`, `ZERION_WALLET_ADDRESS` | Read Zerion endpoints |
| x402 | `ZERION_X402_PRIVATE_KEY`, `ZERION_WALLET_ADDRESS` | Read Zerion analytics and pay data fees from a dedicated Base wallet |

Partial or conflicting configuration stops startup. A call-time API failure returns a typed error and keeps `fallback: "none"`.

`ZerionAPIReader` maps per-asset positions and wallet transactions. Positions use one request. Transactions follow `links.next` for up to `max_pages`, which defaults to 20. A malformed, repeated, or off-host cursor raises `ZerionAPIPaginationError`. Missing asset symbols and unmapped operations are logged and skipped instead of invented.

Asset indicators read `fixtures/price_history.json` in every mode. A live portfolio source does not make that price series live. DCA previews accept optional quote fields from the caller. The package does not call Zerion's swap quote endpoint in 0.4.0.

## Authority and state

The observed wallet supplies an address. Scout has no signer for that wallet. Public tools cannot connect it, submit a transaction, execute a trade, or verify settlement.

x402 creates a separate authority boundary. Its SDK session holds a payment-wallet signer and can spend USDC for analytics. Scout reserves the per-payment cap before every payment payload, including recovery. The process-lifetime budget defaults to 21 reservations. Payment failures and budget stops are non-retryable because settlement can be ambiguous.

`set_alert` writes `.scout/alerts.json`. `check_alerts` reads that file when called. There is no scheduler or push channel.

`preview_id` identifies one generated preview. It is not an authorization token. `approval_state=required` is a label because no approver registry exists.

The runtime tree contains no execution adapter. [`tests/test_execution_boundary.py`](../tests/test_execution_boundary.py) checks the file boundary and pins the MCP registry to the public tools.

The watch report makes one wallet observation. PnL, analysis, DCA windows, and local alert results share that snapshot. This keeps x402 cost tied to one read chain and prevents panel count from multiplying requests.

## Host packaging

Claude Code reads the root plugin, skills, `.mcp.json`, and Python runtime. The generated Codex plugin carries skills and metadata. Codex tools require the root stdio route. Generic MCP clients start `zpm-mcp` directly.

[`scripts/build_release_zip.py`](../scripts/build_release_zip.py) verifies each packaged route, generated-file parity, local links, checksums, and byte-for-byte reproduction.

Tool descriptors carry the package version. A breaking input or output schema needs a new tool name or major package version. Current evidence remains local and offline unless a claim names a live smoke test.
