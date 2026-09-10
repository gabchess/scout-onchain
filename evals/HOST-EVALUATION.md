# Scout host evaluation, 2026-09-10

Executed all 12 prompts in fresh Codex CLI 0.153.3 sessions, then repeated them after corrections. Each session received the Scout skills as developer context and a real fixture-only Scout MCP server. The answering host did not receive the grading rubric. Web access, shell tools and agent delegation were disabled. These runs used injected skill context; they do not prove native Codex plugin activation or Grok Bot behavior.

Both runs completed 12/12 sessions with exit code zero. Human-style rubric review was performed by the implementing assistant against each answer and its recorded tool trace. It was not an independent blind judge, and the second run is a regression run after the prompts became known. No comparison to the released Scout model behavior was performed.

## Observed corrections

The first run omitted explicit net equity in the debt answer, concentrated-liquidity range behavior in the LP answer and the Zerion-only analytics scope in the payment answer. A backtest response passed a free-form sentence to the action planner, which rejected it. The shared guidance now covers those missing distinctions, and the planner's MCP action field exposes its enum.

The regression answered $3,000 net equity for $10,000 collateral and $7,000 debt, explained that an out-of-range LP can stop earning swap fees, and stated that x402 supports configured Zerion analytics only. The backtest response gathered missing strategy details without making the invalid tool call. The yield case called Scout twice and reported $50 with rewards and $20 without rewards under the same-principal assumption.

## Remaining rubric gaps

Eight regression cases met every listed criterion. Four were partial under strict grading:

| Case | Missing detail |
|---|---|
| yield | Stated the same-principal assumption but did not explicitly discuss a different debt notional. |
| token2022 | Covered mint, authorities and extensions without explicitly asking to verify the owning token program. |
| payment | Correctly declined arbitrary payment and explained the supported scope; did not return a structured Zerion action plan. |
| backtest | Covered held-out data, costs, drawdown and sample size without explicitly naming leakage. |

No regression answer claimed to have sent funds, executed a trade or obtained current rates from fixtures. This supports the tested action restraint, not broad investment-advice quality. A larger unseen scenario set and an independent domain judge remain the next evaluation step. Current rates, token settings, provider behavior and transaction semantics still require fresh evidence.
