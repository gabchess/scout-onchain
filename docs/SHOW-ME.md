# Show me: runtime shape

```text
Synthetic fixture (default) or optional Zerion source
  -> ReadOnlyHost.get_portfolio_snapshot()
  -> PortfolioSnapshot
  -> ReadOnlyHost.get_pnl()
  -> PnlResult

DCA text
  -> ReadOnlyHost.parse_dca_request()
  -> partial DcaIntent
  -> clarification, never inference
  -> ReadOnlyHost.preview_dca()
  -> approval_state = required
  -> execution_available = false
```

The important boundary is:

```text
proposal != submission != confirmation != verification
```

The host and MCP server have no observed-wallet connection, trade-signing, submission, or execution path. Zerion mode reads per-asset positions and mapped transactions. x402 can sign and pay data fees from a separate payment wallet.

Execution boundary: not implemented in this host. A DCA request ends at a complete, approval-required preview. Wallet connection and execution are outside the current capability.
