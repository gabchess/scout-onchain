---
name: portfolio-intelligence
description: Answers portfolio and PnL questions and produces approval-required DCA previews
---

# Portfolio intelligence

## Scope

Use the fixture-backed host or optional MCP server to:

- observe the current portfolio snapshot;
- calculate explainable USD PnL;
- parse a DCA request into explicit fields;
- build a complete preview that remains approval-required.

The default source is synthetic fixture data. An operator can configure API-key
or x402 Zerion access. Say which source was used. x402 can spend USDC from its
dedicated payment wallet; never ask the user to paste its private key in chat.

## Safety rules

- Never ask for, store, or repeat API keys, signing keys, recovery phrases, or wallet secrets.
- Never sign, submit, execute, route, or claim settlement of a trade.
- Never infer a chain, schedule, source wallet, destination wallet, amount, or asset.
- Keep the boundaries distinct: observe, calculate, propose, approve, execute, verify.
- A preview is a proposal. It must say `approval_state=required` and `execution_available=false`.
- If data is missing or stale, state the gap instead of filling it with a guess.

## Workflow

1. Identify whether the user wants an observation, calculation, parsed intent, or preview.
2. Call only the matching read-only tool: `get_portfolio_snapshot`, `get_pnl`,
   `parse_dca_request`, or `preview_dca`.
3. Report the source, observed time, assumptions, formulas, and uncertainty when relevant.
4. For DCA, check all six fields: amount, asset, chain, schedule, source, destination.
5. Ask a short clarification question for each missing field. Do not preview incomplete intent.
6. For a complete intent, show the preview and its approval-required status. Stop there.

## Output shape

For portfolio answers, include the relevant holdings or PnL result and the evidence boundary.
For DCA answers, include parsed fields, missing fields, assumptions, fee/slippage details, and
approval state. Never use words such as "sent", "bought", or "completed" unless the user is
quoting a past event from an external source, and label that source clearly.

## Direct Python fallback

If MCP is unavailable, install the package with `pip install -e .` and use:

```python
from scout_portfolio_manager.host import default_host

host = default_host()
print(host.get_portfolio_snapshot())
print(host.get_pnl())
print(host.get_pnl(asset="ETH"))
```

The host exposes no execution tool. `call_tool("execute", ...)` must be rejected.
