# Scout fresh holdout review

The amended runtime scored **95.52%** on the separately frozen six-case holdout. **6/6 cases pass, and all 8 critical criteria receive full credit.** The holdout passes its preregistered gate. Of 30 criteria, 26 receive full credit and 4 receive partial credit; none receive zero credit.

The answers reject issuer-proof claims after ordinary delegate revocation, apply debt-asset liquidation thresholds, respect withdrawal timing, and reject accounting a wrong-recipient mint as treasury cash. All required numerical results are correct within the frozen tolerances.

## Independence and evaluated scope

Holdout SHA-256: `f740769c3e0a2f254cbd9ece8aa6a9a6e9da22812d2d533bdfeea18d853d0143`. The six cases and rubric were frozen before the reviewer received amended answers and before the candidate run. The reviewer did not read the Scout changes. These cases target categories learned from the baseline and include two broader controls, so this is a fresh targeted holdout with explicit limits on generalization.

The manifest describes a dirty frozen worktree based on `7d2e5dd8ad5cd5045c57f2b7bdf1280b6fab3ff9`, using runtime SHA-256 `5319d9d2619783c6f36939da93f82faf4105cd752b73a5594a107c63ecb3f254`. `amended-source-proof.json` maps that same recorded runtime hash to public commit `565be97350a86fa7606aa9ed17bdf9058a5297eb`. The reviewer verified equality of the recorded hashes across the regression manifest, holdout manifest and proof file. The reviewer did not recompute the commit hash from Scout source. The run reports that its runtime stayed unchanged.

Each of the six manifest entries has exit_code=0. Grading uses the frozen rubric rather than host exit status. The original 12-case baseline remains failed, and the four exposed-case regression result stays separate. No combined score is presented.

## Scores

| Case | Score | Gate |
|---|---:|---|
| HLD-01 | 100.00% | Pass |
| HLD-02 | 95.83% | Pass |
| HLD-03 | 92.31% | Pass |
| HLD-04 | 91.67% | Pass |
| HLD-05 | 100.00% | Pass |
| HLD-06 | 93.33% | Pass |

| Severity | Full | Partial | Zero | Total |
|---|---:|---:|---:|---:|
| critical | 8 | 0 | 0 | 8 |
| major | 14 | 3 | 0 | 17 |
| minor | 4 | 1 | 0 | 5 |

The original scoring rules remain in force: critical=5, major=2, minor=1; pass=1, partial=0.5, fail=0. Equal-weight cases produce the suite mean. A case needs every critical criterion at full credit and at least 80%; the suite needs every critical criterion at full credit and a mean of at least 85%.

## Remaining omissions

**HLD-03-c4, major partial:** The answer names Ethereum finalization as the remaining step. It does not instruct verification that finalization succeeded and the expected spendable balance arrived. Preserve that distinction when converting a bridge state into treasury availability.

**HLD-06-c4, major partial:** The wrong-recipient analysis and refusal to repeat the burn are correct. The recovery explanation omits preserving transaction hashes/domains and investigating how the wrong address entered the instructions. Add those steps to an incident handoff.

**HLD-04-c4, major partial under the frozen rubric:** The answer explains isolated liquidation and funding reversal, but omits a separate basis/mark divergence discussion. The prompt asks for two independent mechanisms and the answer supplies them. The frozen criterion is more specific than that request. This report retains the strict partial score and makes the mismatch visible rather than silently revising the rubric.

As a sensitivity check, awarding HLD-04-c4 full credit for satisfying the prompt's two-mechanism request would yield **96.91%**. The gate would still pass. This alternate is not the official frozen score.

HLD-02-c5 receives minor partial credit: it distinguishes eligibility from completed liquidation and flags intervening liquidation, but omits debt accrual and real oracle-timing uncertainty.

## Source discrepancy

HLD-01 correctly identifies the current permanent delegate as the authority for changing that role. The overview page's mint-authority wording is imprecise. The reviewer verified the [official Token-2022 processor](https://raw.githubusercontent.com/solana-program/token-2022/main/program/src/processor.rs), whose PermanentDelegate branch validates the existing delegate. The frozen criterion already says relevant mint-level authority, so full credit requires no rubric change. See [the source addendum](holdout-source-addendum.md).

The candidate attributes its discussion to curated documentation and notes a conflicting imported glossary. Its own run did not inspect live program code. The precise authority statement should cite the processor or extension guide directly when promoted into durable documentation.

## Per-criterion evidence

Evidence below paraphrases or normalizes answer formatting. Exact answers and traces are linked, with hashes stored in `holdout-grades.json`.

### HLD-01

[Answer](holdout-run/HLD-01-answer.md) · [Completed tool calls](holdout-run/HLD-01-tools.jsonl)

- **HLD-01-c1 · major · pass:** Gross transfer 8,030.000000; uncapped fee 60.225000; capped fee 30.000000; supplier receives 8,000.000000 spendable tokens.
- **HLD-01-c2 · critical · pass:** Revoking ordinary account delegates leaves that authority intact. The treasury owner cannot remove it.
- **HLD-01-c3 · critical · pass:** The issuer-proof claim is false; K can transfer or burn tokens from treasury and supplier accounts.
- **HLD-01-c4 · major · pass:** The current permanent delegate, K, can change or disable the authority with SetAuthority. Holding the mint authority alone does not grant that power.
- **HLD-01-c5 · minor · pass:** Requests finalized mint state and an authority-change transaction, other control settings, backing/redemption evidence, payroll-size liquidity and settlement timing.

Reviewer notes: c4 is supported by direct program-source verification after reading this answer. The overview page's mint-authority wording is imprecise; processor validates the current permanent delegate. Frozen criterion and reference already require the relevant mint-level authority without naming the minting authority, so no rubric change is needed.

Frozen references: [Source 1](https://solana.com/docs/tokens/extensions/permanent-delegate), [Source 2](https://solana.com/docs/tokens/extensions/transfer-fees).

### HLD-02

[Answer](holdout-run/HLD-02-answer.md) · [Completed tool calls](holdout-run/HLD-02-tools.jsonl)

- **HLD-02-c1 · major · pass:** HF=31,200/(3P); initial HF is 1.30 and the boundary ETH price is $10,400.
- **HLD-02-c2 · critical · pass:** An oracle price above $10,400 makes the account eligible; equality does not establish that liquidation occurred.
- **HLD-02-c3 · major · pass:** At the supplied lending oracle the HF is 1.04; the DEX quote alone cannot establish eligibility or prove liquidation.
- **HLD-02-c4 · major · pass:** Repays 0.523809524 ETH, or $5,500, to restore HF to 1.20.
- **HLD-02-c5 · minor · partial:** The repayment assumes no intervening liquidation. The answer distinguishes a threshold from an observed liquidation, but omits debt accrual and real oracle timing.

Reviewer notes: c5: Includes an execution-timing caveat and distinction from actual liquidation, but does not discuss debt accrual or real oracle-timing uncertainty. Partial minor criterion.

Frozen references: [Source 1](https://aave.com/help/borrowing/liquidations).

### HLD-03

[Answer](holdout-run/HLD-03-answer.md) · [Completed tool calls](holdout-run/HLD-03-tools.jsonl)

- **HLD-03-c1 · major · pass:** $4,600 cash plus $500 withdrawable lending funds gives $5,100, leaving a $3,900 shortfall.
- **HLD-03-c2 · critical · pass:** The bridge contributes $0; the remaining $7,500 lending claim stays unavailable through the deadline.
- **HLD-03-c3 · major · pass:** The challenge period completes five full days from today, three days after the payment deadline.
- **HLD-03-c4 · major · partial:** An Ethereum finalization transaction remains necessary to release the funds. Successful settlement and balance verification are not discussed.
- **HLD-03-c5 · major · pass:** The full $8,000 claim cannot support the payment because only $500 is withdrawable under the stated pool-liquidity fixture.

Reviewer notes: c4: Correctly requires subsequent Ethereum finalization, but omits verifying successful settlement and the received balance. Partial major criterion.

Frozen references: [Source 1](https://docs.optimism.io/op-stack/bridging/withdrawal-flow), [Source 2](https://www.aave.com/help/supplying/withdraw-tokens).

### HLD-04

[Answer](holdout-run/HLD-04-answer.md) · [Completed tool calls](holdout-run/HLD-04-tools.jsonl)

- **HLD-04-c1 · major · pass:** Funding received $78.90; funding paid $210.41; execution fees $180; net loss $311.51; return −0.3115%.
- **HLD-04-c2 · critical · pass:** The founder should reserve the $500 separately because the fixture generates a loss and paying the bill would consume principal.
- **HLD-04-c3 · major · pass:** Future funding can change magnitude or sign even when the price hedge holds.
- **HLD-04-c4 · major · partial:** Spot gains do not automatically replenish isolated margin, and liquidation can precede a recovery in price. A separate basis/mark divergence explanation is absent.
- **HLD-04-c5 · minor · pass:** The combined opening delta is approximately zero, which provides no cashflow promise. Withdrawal timing remains unspecified.

Reviewer notes: c4: Addresses isolated margin and external spot gains but omits the separate basis/mark divergence explanation required by the frozen rubric. Rubric specificity caveat: the prompt asks for two independent failure mechanisms, and the answer supplies funding reversal and isolated liquidation. The frozen c4 additionally requires basis/mark divergence. Strict scoring remains partial; a sensitivity calculation can award c4 full credit to reflect satisfaction of the prompt's stated two-mechanism request.

Frozen references: [Source 1](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding), [Source 2](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/liquidations).

### HLD-05

[Answer](holdout-run/HLD-05-answer.md) · [Completed tool calls](holdout-run/HLD-05-tools.jsonl)

- **HLD-05-c1 · major · pass:** Initial position is 33⅓ A plus 10,000 stablecoins, worth $17,500.
- **HLD-05-c2 · critical · pass:** Ending principal inventory is 0 A and 20,000 stablecoins, worth $20,000.
- **HLD-05-c3 · major · pass:** Including fees yields $20,500 versus a $26,666.67 holding benchmark, a $6,166.67 or 23.125% shortfall.
- **HLD-05-c4 · major · pass:** Including fees, the gain over starting capital is $3,000, or 17.14%.
- **HLD-05-c5 · minor · pass:** Continued trading above $400 adds no fees; the $500 is the exact supplied prior fee amount.

Frozen references: [Source 1](https://app.uniswap.org/whitepaper-v3.pdf), [Source 2](https://developers.uniswap.org/docs/liquidity/overview).

### HLD-06

[Answer](holdout-run/HLD-06-answer.md) · [Completed tool calls](holdout-run/HLD-06-tools.jsonl)

- **HLD-06-c1 · critical · pass:** The transfer contributes 0 USDC to Y’s available treasury cash.
- **HLD-06-c2 · major · pass:** Reconciles 15,000 = 14,940 delivered to X + 60 fee and identifies completed delivery to the wrong recipient.
- **HLD-06-c3 · critical · pass:** Rejects the proposed second burn because it creates another 15,000 USDC outflow and does not reverse the first.
- **HLD-06-c4 · major · partial:** Recovery depends on X’s controller or an independently established process. It omits a preservation plan for hashes/domains and investigation of how X entered the instruction.
- **HLD-06-c5 · minor · pass:** The fixture establishes no treasury power to revoke or redirect the finalized mint; the consumed nonce prevents minting to Y through replay.

Reviewer notes: c4: Correctly conditions recovery on legitimate authority, but does not instruct preservation of transaction hashes/domains or investigation of how X entered the instruction. Partial major criterion; no claim of automatic reversal.

Frozen references: [Source 1](https://developers.circle.com/cctp/references/technical-guide).

## Tool and claim boundary

The inspected traces contain three completed `search_defi_knowledge` calls, in HLD-01, HLD-04 and HLD-05, with no recorded tool error. HLD-02, HLD-03 and HLD-06 use no tool. No execution, signing, preparation, or other action item appears. The answers consistently use the supplied hypothetical states and make no observed false-live or execution claim.

This provides evidence for retrieval-assisted explanations in the injected-context fixture setup. It does not evaluate all available tools or native plugin activation. The host still warns about its experimental discovery option and skill catalog budget. The exact model remains recorded only as the host default.

## Permitted package claim and limits

A supported claim is: **After targeted corrections, the amended Scout runtime passed a separate six-case DeFi holdout, with all eight critical criteria met. The test used hypothetical fixtures and independent AI grading.** Cite this report with the runtime hash and public-commit correspondence.

Keep the original baseline result and exposed-case regression visible alongside that statement. Avoid claims of broad DeFi expertise, human expert approval, dependable returns, live-provider readiness, or production-safe financial execution. None is established here.

This is independent AI review, not human expert certification. One AI authored and graded the holdout. There are no repeated runs or measured inter-rater agreement. A selected sample of six cases cannot establish population accuracy, a valid 95% population confidence interval, statistical power or model superiority. A larger representative sample and a second reviewer would support stronger claims; native activation and provider execution need separate evidence.
