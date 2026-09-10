# Scout exposed-case regression review

The four amended answers score **97.92%**, and **4/4 pass** the frozen case gates. The subset passes its screening gate. These same cases averaged **87.83%** in the baseline, an observed change of **10.09 percentage points**. The original 12-case failed-gate verdict remains unchanged.

This is regression evidence on questions exposed after the first run. A separate six-case holdout was frozen before these amended answers were read. Do not combine their scores into a new supposedly unseen baseline.

## Evaluated snapshot

The run manifest records base revision `7d2e5dd8ad5cd5045c57f2b7bdf1280b6fab3ff9`, **source_dirty=true**, runtime SHA-256 `5319d9d2619783c6f36939da93f82faf4105cd752b73a5594a107c63ecb3f254`, and context SHA-256 `140cf457a73e06a2c5726e62dca054a0778f5e0ac37c5859966b12827eeda966`. Thus this is an amended frozen working snapshot based on that commit, not the clean commit itself. The runtime was unchanged during the run. The four-case subset matches the original suite entries exactly and its file hash matches the run manifest.

Only four manifest entries with exit_code=0 were graded. Zero host exit is infrastructure completion. Quality uses the original severity weights and pass rules.

## Results

| Case | Original score | Regression score | Case gate |
|---|---:|---:|---|
| DFI-02 | 83.33% | 91.67% | Pass |
| DFI-05 | 90.91% | 100.00% | Pass |
| DFI-06 | 83.33% | 100.00% | Pass |
| DFI-12 | 93.75% | 100.00% | Pass |

Criterion totals: **18 full credit, 0 partial, 1 zero credit**. The remaining zero-credit criterion is minor DFI-02-c5: the answer does not directly explain the stressed account's limited residual buffer.

## Changes supported by the answers

- DFI-02-c3: now states HF<1 makes the account eligible for liquidation and distinguishes the boundary from an observed liquidation.
- DFI-05-c3: now names proof, fault-challenge completion and L1 finalization.
- DFI-06-c3: now explicitly states an individual holder cannot revoke the permanent delegate.
- DFI-12-c5: now explains funding can change magnitude or sign, alongside margin location and transfer constraints.

## Evidence by criterion

### DFI-02

[Answer](regression-run/DFI-02-answer.md) · [Completed tool calls](regression-run/DFI-02-tools.jsonl)

- **DFI-02-c1 · critical · pass**: Uses the sum of collateral values times their liquidation thresholds, divided by debt value. The stressed debt denominator includes 20,000 × 1.05.
- **DFI-02-c2 · major · pass**: Current HF is 1.385; stressed HF is 1.0957.
- **DFI-02-c3 · major · pass**: The boundary ETH price is $1,390.625. The answer now says HF below 1 makes a position eligible, and equality does not establish that liquidation occurred.
- **DFI-02-c4 · major · pass**: The repayment is 3,142.857142 D units, costing approximately $3,300 at the stipulated price.
- **DFI-02-c5 · minor · fail**: The general eligibility rule is present, but the response does not interpret this stressed account’s limited remaining buffer.

The previous major boundary omission is repaired. Minor c5 remains unaddressed: no direct assessment that the stressed account's remaining buffer is limited.

### DFI-05

[Answer](regression-run/DFI-05-answer.md) · [Completed tool calls](regression-run/DFI-05-tools.jsonl)

- **DFI-05-c1 · critical · pass**: Arbitrum lending claims and the OP withdrawal each contribute $0. The $2,000 withdrawable on Arbitrum has no route that meets the deadline.
- **DFI-05-c2 · major · pass**: Usable funds are $14,591.40 and the shortfall is $5,408.60. Selling U yields 7,000 × 0.98 × 0.99 = $6,791.40.
- **DFI-05-c3 · major · pass**: The withdrawal requires proof, completion of the fault-challenge period and L1 finalization. The remaining $8,000 lending claim is unavailable for withdrawal.
- **DFI-05-c4 · major · pass**: Keeps upcoming obligations on the settlement chain, with separate gas and operating reserves sized around stressed exit times.

### DFI-06

[Answer](regression-run/DFI-06-answer.md) · [Completed tool calls](regression-run/DFI-06-tools.jsonl)

- **DFI-06-c1 · major · pass**: The two capped transfer fees produce 10,000 → 9,900 → 9,800 spendable tokens.
- **DFI-06-c2 · critical · pass**: Excludes the deposit because the simulated hook denies the vault transfer. The denied transfer delivers zero, and simulation changes no state.
- **DFI-06-c3 · critical · pass**: The issuer’s permanent delegate can transfer or burn tokens across the mint’s accounts. An individual holder cannot revoke that authority.
- **DFI-06-c4 · major · pass**: Checks exact mint identity, Token-2022 ownership, active and scheduled fees, spendable balances, account controls and hook/vault compatibility.
- **DFI-06-c5 · minor · pass**: Withheld fees cannot be forwarded as spendable tokens.

### DFI-12

[Answer](regression-run/DFI-12-answer.md) · [Completed tool calls](regression-run/DFI-12-tools.jsonl)

- **DFI-12-c1 · major · pass**: Funding costs $345.21, fees cost $120, net carry is −$465.21 and the return on $110,000 is −0.423%.
- **DFI-12-c2 · critical · pass**: The short pays funding on the $100,000 notional at 18% × 7/365.
- **DFI-12-c3 · major · pass**: Theoretical isolated equity is −$2,000, current notional is $112,000 and maintenance is $5,600. The 4.762% boundary is crossed before the full 12% move.
- **DFI-12-c4 · critical · pass**: The spot gain remains in a separate Ethereum wallet and cannot automatically support isolated margin; liquidation can break the hedge.
- **DFI-12-c5 · major · pass**: Future funding can change magnitude or sign. The answer also explains the limits of matched price exposure and the uncertainty of exit liquidity and transfer timing.

## Tool and claim boundaries

The traces contain 4 completed MCP calls, all `search_defi_knowledge`, with 0 recorded tool errors. No execution or other action item appears. No answer claims live account verification or an executed transaction. The same host skill-budget and experimental discovery warnings remain; this demonstrates injected-context/fixture retrieval behavior, while native plugin activation remains untested.

## Limits

One independent AI reviewer graded these answers without reading the amended code. This is not human expert certification. With four selected exposed cases and one run per case, the observed change does not establish population improvement, statistical significance or a 95% population confidence interval. The precise host model remains recorded only as the default. See the separate holdout review for unseen-question evidence once complete.
