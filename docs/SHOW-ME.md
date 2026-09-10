# Show me Scout

Scout is a portfolio tool set for an LLM agent. The agent selects a route from the user's request.

```text
user request
  |
  +-- holdings or activity --> portfolio snapshot
  |
  +-- performance ---------> snapshot --> PnL
  |
  +-- DCA decision --------> portfolio context
  |                          + synthetic market indicators
  |                          + current DCA window
  |                          + clarified intent
  |                          + approval-required proposal
  |
  +-- saved condition -----> local alert rule --> on-demand check
  |
  +-- broad review --------> one snapshot --> static watch report
```

Portfolio snapshots can use the bundled fixture or Zerion. API-key mode reads positions and mapped transactions. x402 mode pays for analytics from a separate Base wallet and reports its remaining process budget.

DCA proposals may use quote values supplied by the host. Optional Zerion CLI preparation can obtain an unsigned proposal. Market indicators use bundled synthetic history with low confidence.

The runtime boundary is fixed:

```text
observe --> calculate --> propose --> preview
                                      |
                                      stop
```

Every complete DCA preview has `approval_state=required` and `execution_available=false`. The package has no observed-wallet signer, trade adapter, submission tool, or settlement verifier.
