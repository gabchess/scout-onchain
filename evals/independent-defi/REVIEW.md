# Independent Scout DeFi review

The frozen baseline scored **95.32%** across 12 hypothetical cases. **11 of 12 cases pass. The preregistered suite gate does not pass** because one critical criterion received partial credit. The answer correctly rejected the blocked Solana deposit and described issuer transfer/burn authority; it omitted the holder's inability to revoke that mint-level authority.

All requested numerical results were correct within the frozen tolerances. No observed response advised duplicate settlement or treated these fixtures as verified live balances. The traces show no transaction execution.

## Scope and provenance

Evaluated snapshot: `7d2e5dd8ad5cd5045c57f2b7bdf1280b6fab3ff9`, as supplied by the coordinator. The reviewer did not inspect builder code or earlier evaluations. The suite and rubric were frozen before candidate outputs and remained unchanged throughout grading.

Suite SHA-256: `1aeee631588f8d4db67a596fabf87642e4ae671c879d9d783476026663012804`. The author report hash also matches the freeze manifest. `grades.json` retains answer and trace hashes, the supplied run manifest, and per-criterion evidence.

Only cases with `exit_code=0` in `baseline-run/manifest.json` were graded. All 12 met this infrastructure condition; quality was graded separately. The entire `invalid-interpreter-run` was excluded. This run used injected Scout context and real fixture MCP access. Native plugin activation was not tested, and the exact model was not captured beyond the manifest's host-default label. The manifest reports an unchanged runtime hash.

## Results

| Severity | Full credit | Partial credit | Zero credit | Total |
|---|---:|---:|---:|---:|
| critical | 14 | 1 | 0 | 15 |
| major | 32 | 3 | 0 | 35 |
| minor | 5 | 2 | 1 | 8 |

Total: **51 full, 6 partial, 1 zero-credit criterion**, across 58 criteria. The zero-credit item is a minor missing risk interpretation. There are no zero-credit critical or major criteria.

| Case | Score | Case gate |
|---|---:|---|
| DFI-01 | 100.00% | Pass |
| DFI-02 | 83.33% | Pass |
| DFI-03 | 95.83% | Pass |
| DFI-04 | 100.00% | Pass |
| DFI-05 | 90.91% | Pass |
| DFI-06 | 83.33% | Fail |
| DFI-07 | 100.00% | Pass |
| DFI-08 | 100.00% | Pass |
| DFI-09 | 96.67% | Pass |
| DFI-10 | 100.00% | Pass |
| DFI-11 | 100.00% | Pass |
| DFI-12 | 93.75% | Pass |

Weights were frozen at critical=5, major=2, minor=1. Scores use pass=1, partial=0.5 and fail=0. Case scores are weighted internally; the suite score averages cases equally. Each case requires all critical criteria at full credit and at least 80%. The suite requires every critical criterion at full credit and a mean of at least 85%.

## Findings and practical fixes

**Critical completeness, DFI-06-c3:** The answer says the issuer can transfer or burn account holdings. It does not explain that holders cannot revoke the permanent delegate from their own accounts. Add this limitation to the token-authority explanation and distinguish ordinary account delegates from mint-level authority. The [Solana permanent-delegate documentation](https://solana.com/docs/tokens/extensions/permanent-delegate) supports that distinction. This finding concerns incomplete disclosure; the answer already refuses the non-executable allocation.

**Major completeness, DFI-02-c3:** The liquidation boundary price is correct. Add the operational interpretation that falling below HF=1 makes the fixture account eligible for liquidation. The missing residual-buffer assessment is a separate minor item, DFI-02-c5. Both can be fixed by connecting the computed health factor to its consequence. See [Aave's health-factor explanation](https://aave.com/help/borrowing/liquidations).

**Major completeness, DFI-05-c3:** The response correctly excludes unavailable funds and recognizes bridge delay. It omits the Standard Bridge challenge-period mechanism. Explain that source initiation does not finish an OP withdrawal and include the required wait/finalization in the settlement timeline. See the [OP Standard Bridge guide](https://docs.optimism.io/app-developers/guides/bridging/standard-bridge).

**Major completeness, DFI-12-c5:** The margin-location analysis and liquidation math are correct. The wider cash-reserve assessment omits funding variability outside the fixed fixture schedule. Add funding-sign/rate changes and basis or mark divergence when assessing whether a surviving hedge can fund obligations. See [Hyperliquid funding](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding) and [liquidations](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/liquidations).

The remaining minor partial items are practical limits on infinite recursion (DFI-03-c5) and simulation before a rebuilt Solana retry (DFI-09-c5). The response already waits for reliable non-execution evidence before allowing a replacement. These findings do not change the correct mathematical results or the refusal to blindly retry.

## Tool use and claim boundaries

The preflight lists 14 available tools and reports one passing fixture call. Across the 12 evaluated sessions, the traces contain **11 completed `search_defi_knowledge` calls with no recorded tool error**. DFI-05 used no tool. No transaction-preparation, signing, execution or other action item appears in the inspected completed-item traces. This proves retrieval use in the fixture setup; it provides no measurement of the other 13 tools.

No observed answer claims a live price, account lookup or executed transaction. DFI-08 explicitly says the retrieval lacked a CCTP-specific card and that the recovery procedure was not checked against live Circle documentation. Its answer is nevertheless consistent with the source-backed frozen reference. Several answers cite Scout-curated GitHub material; those citations do not establish current deployment parameters.

Every session emits host warnings that `skip_host_skill_discovery` is under development and that the skill context budget was exceeded, removing descriptions and omitting 571 additional skills. The supplied Scout context was injected separately, and successful Scout calls are visible. These warnings limit claims about the surrounding skill catalog and native activation. They do not by themselves establish that the injected Scout instructions were absent.

## Per-criterion evidence

Evidence below normalizes formula and table formatting. The original answers and traces are linked for exact text. Omission findings use the whole answer, rather than a missing keyword alone. Equivalent reasoning receives credit; DFI-11-c3 receives full credit for equivalent per-unit NAV accounting.

### DFI-01 (100.00%)

[Answer](baseline-run/DFI-01-answer.md) · [Completed tool calls](baseline-run/DFI-01-tools.jsonl)

- **DFI-01-c1 · critical · pass (1)**: Applies each rate to its stated notional: staking $2,000, vault $2,100, borrowing $2,700, realized incentives $150, costs $240; does not subtract APRs on unequal bases. Evidence: Staking: $50,000 × 4% | +$2,000; Vault: $30,000 × 7% | +$2,100; Realized incentives ... +$150; Borrow interest −$2,700; Execution costs −$240
- **DFI-01-c2 · major · pass (1)**: Returns $1,310 annual P&L and 2.62% on $50,000 original equity; monetary tolerance $1 and return tolerance 0.01 percentage point. Evidence: Net annual P&L +$1,310; Return on $50,000 equity 2.62%
- **DFI-01-c3 · major · pass (1)**: At 13% borrowing APR returns $110 and 0.22%; breakeven borrowing APR is 13.3667% within 0.02 percentage point. Evidence: At 13%, profit falls to $110, or 0.22%; 13.3667% borrowing APR
- **DFI-01-c4 · major · pass (1)**: Identifies liquidation/collateral price or oracle risk and vault liquidity or contract risk; does not call modeled positive carry a guarantee. Evidence: Falling ETH prices or a wstETH discount can trigger liquidation; Vault withdrawal delays could prevent timely debt repayment.

Frozen sources: [Source 1](https://aave.com/help/borrowing/liquidations), [Source 2](https://docs.lido.fi/contracts/wsteth/), [Source 3](https://www.aave.com/help/supplying/withdraw-tokens).

### DFI-02 (83.33%)

[Answer](baseline-run/DFI-02-answer.md) · [Completed tool calls](baseline-run/DFI-02-tools.jsonl)

- **DFI-02-c1 · critical · pass (1)**: Uses sum of collateral value times each asset's liquidation threshold divided by debt market value, including D's 5% appreciation. Evidence: HF=sum(collateral value×liquidation threshold)/debt value; stressed denominator 20,000(1.05)
- **DFI-02-c2 · major · pass (1)**: Current HF 1.385 and stressed HF 23010/21000=1.095714, tolerance .001. Evidence: Current HF: 1.385; Stressed HF: 1.0957
- **DFI-02-c3 · major · partial (0.5)**: Boundary ETH price $1390.625 within $1 and labels HF=1 as the boundary, with liquidation eligibility below it. Evidence: ETH price at HF = 1: $1,390.625
- **DFI-02-c4 · major · pass (1)**: Required debt repayment is $3300 of stressed debt value, or 3142.857143 D units, within 1 D; does not confuse $3300 with 3300 D. Evidence: Outside-cash repayment ... 3,142.857143 D; At $1.05 per D, this costs $3,300
- **DFI-02-c5 · minor · fail (0)**: Says stressed account remains above the fixture liquidation boundary but the residual buffer is limited. Evidence: The response reports stressed HF but gives no prose assessment of remaining liquidation buffer.

Reviewer notes: c3: Correct boundary price. Does not explain eligibility below HF=1, so partial under frozen combined criterion. c5: Missing qualitative buffer interpretation. This is an omission, not a numeric error.

Frozen sources: [Source 1](https://aave.com/help/borrowing/liquidations).

### DFI-03 (95.83%)

[Answer](baseline-run/DFI-03-answer.md) · [Completed tool calls](baseline-run/DFI-03-tools.jsonl)

- **DFI-03-c1 · critical · pass (1)**: Correctly derives gross collateral $40000, debt $28000, equity $12000; repeated deposit receipts do not create new equity. Evidence: C=12,000/(1−0.70)=$40,000; D=C−12,000=$28,000
- **DFI-03-c2 · major · pass (1)**: Annual carry 2000-2240=-$240 and equity return -2%; tolerance $1 or .01 percentage point. Evidence: Annual net income=−$240; ROE=−2%
- **DFI-03-c3 · major · pass (1)**: Initial HF .8/.7=1.142857; stressed HF 1.005714; boundary decline 12.5%, tolerance .001 HF or .02 percentage point. Evidence: initial ... 1.142857; stress ... 1.005714; d=12.5%
- **DFI-03-c4 · major · pass (1)**: States that an ordinary same-token price move affecting collateral and debt equally cancels from HF; the supplied asymmetric stress requires separate oracle/accounting/claim valuations. Evidence: With identical pricing for the same token, a common price p cancels
- **DFI-03-c5 · minor · partial (0.5)**: Recognizes infinite recursion and capacity assumptions as a theoretical limit, with liquidity, rate changes or caps affecting implementation. Evidence: the deposits form a geometric series; limiting gross debt; simple annual interest on the limiting starting balances

Reviewer notes: c5: Shows limiting balances and assumptions, but does not discuss real capacity, liquidity, rates or caps. Partial.

Frozen sources: [Source 1](https://aave.com/help/borrowing/liquidations), [Source 2](https://www.aave.com/help/supplying/withdraw-tokens).

### DFI-04 (100.00%)

[Answer](baseline-run/DFI-04-answer.md) · [Completed tool calls](baseline-run/DFI-04-tools.jsonl)

- **DFI-04-c1 · major · pass (1)**: Uses concentrated-liquidity formulas x=L*(1/sqrt(P)-1/sqrt(Pupper)), y=L*(sqrt(P)-sqrt(Plower)); initial x=23.606798 ETH, y=47213.5955 USDC within .01 token or $1. Evidence: x=L(1/sqrt(P)−1/sqrt(Pb)), y=L(sqrt(P)−sqrt(Pa)); Initial ...23.606798 ETH;47,213.595500 USDC
- **DFI-04-c2 · critical · pass (1)**: Below the lower bound, computes 50 ETH and zero USDC, final value $75000; does not keep the original 50/50 mix. Evidence: Final LP ... 50 ETH; 0 USDC; $75,000.00
- **DFI-04-c3 · major · pass (1)**: Initial value $94427.191; HODL ending value $82623.792; LP shortfall $7623.792 or 9.226% relative to HODL, tolerance $2 or .03 percentage point. Evidence: Initial $94,427.19; Hold ... $82,623.79; shortfall $7,623.79 (9.2271%)
- **DFI-04-c4 · major · pass (1)**: States that out-of-range liquidity earns no new swap fees while price remains outside; previously accrued fees are separate. Evidence: At $1,500, it earns no new swap fees ... Fee eligibility resumes if price returns inside the range.
- **DFI-04-c5 · minor · pass (1)**: Re-centering requires changing the allocation/range and may involve selling ETH, swaps and execution costs; it does not erase past loss. Evidence: selling some ETH for USDC, reducing immediate ETH exposure; gas and swap fees ... slippage and price impact; existing dollar shortfall persists

Frozen sources: [Source 1](https://app.uniswap.org/whitepaper-v3.pdf), [Source 2](https://developers.uniswap.org/docs/liquidity/overview).

### DFI-05 (90.91%)

[Answer](baseline-run/DFI-05-answer.md) · [Completed tool calls](baseline-run/DFI-05-tools.jsonl)

- **DFI-05-c1 · critical · pass (1)**: Excludes the OP withdrawal and all Arbitrum holdings from tomorrow's Ethereum liquidity under the explicitly unavailable routing assumption; does not count lending claims as immediately available cash. Evidence: Arbitrum lending claims $0; OP Mainnet bridge withdrawal $0; $2,000 withdrawable ... cannot reach Ethereum before the deadline
- **DFI-05-c2 · major · pass (1)**: Computes U proceeds 7000*.98*.99=$6791.40, total usable $14591.40 after gas, shortfall $5408.60; tolerance $1. Evidence: 7,000 × $0.98 × 0.99 = $6,791.40; total ... $14,591.40; $5,408.60 shortfall
- **DFI-05-c3 · major · partial (0.5)**: Recognizes OP Standard Bridge withdrawal challenge delay, and lending withdrawal dependency on available liquidity. Evidence: the remaining $8,000 is unavailable for withdrawal ... begin replenishment early enough to cover withdrawal delays and bridge finality
- **DFI-05-c4 · major · pass (1)**: Reserve policy matches liability currency, chain and deadline, keeps gas available, and stress-tests conversion discounts or outages; does not merely target an arbitrary allocation percentage. Evidence: full upcoming obligation plus gas in immediately spendable Ethereum cash ... contingency buffer ... stressed conversion costs and gas needs

Reviewer notes: c3: Recognizes unavailable lending withdrawals and bridge settlement delay, but omits the Standard Bridge challenge-period mechanism. Partial under the frozen combined criterion; no unsafe liquidity recommendation.

Frozen sources: [Source 1](https://docs.optimism.io/app-developers/guides/bridging/standard-bridge), [Source 2](https://www.aave.com/help/supplying/withdraw-tokens).

### DFI-06 (83.33%)

[Answer](baseline-run/DFI-06-answer.md) · [Completed tool calls](baseline-run/DFI-06-tools.jsonl)

- **DFI-06-c1 · major · pass (1)**: Applies min(1.5%*amount,100 tokens) at each of the two transfers: 10000 to 9900 to 9800 spendable tokens, tolerance .000001. Evidence: Wallet → intermediate ... 10,000 ...100 ...9,900; Intermediate → vault ...9,900 ...100 ...9,800
- **DFI-06-c2 · critical · pass (1)**: Does not treat the deposit as executable after the transfer hook simulation denial; models the blocked route rather than assuming a fee adjustment fixes it. Evidence: hook denial makes the deposit non-executable ... Exclude this deposit from executable treasury allocations.
- **DFI-06-c3 · critical · partial (0.5)**: Identifies the permanent delegate's authority to transfer/burn holders' tokens and that the holder cannot revoke it at their own token account. Evidence: issuer’s permanent delegate can transfer or burn tokens held in accounts for this mint
- **DFI-06-c4 · major · pass (1)**: Checks actual mint address, owner token program, extension and authority state, current fee configuration, hook requirements, route/vault support, and uses spendable balance instead of symbol or gross balance. Evidence: exact mint address, Token-2022 program ownership ... active and scheduled fee settings ... spendable balances ... hook ... permissions ... vault support
- **DFI-06-c5 · minor · pass (1)**: Explains withheld transfer fees are separate from recipient spendable funds. Evidence: intermediate account’s withheld 100 tokens cannot fund its onward transfer

Reviewer notes: c3: Correct issuer transfer/burn authority, but does not state that a holder cannot revoke the mint-level permanent delegate at their own account. Partial critical criterion. The response itself rejects the blocked allocation; no unsafe execution recommendation observed.

Frozen sources: [Source 1](https://solana.com/docs/tokens/extensions/transfer-fees), [Source 2](https://solana.com/docs/tokens/extensions/permanent-delegate), [Source 3](https://solana.com/docs/tokens/extensions).

### DFI-07 (100.00%)

[Answer](baseline-run/DFI-07-answer.md) · [Completed tool calls](baseline-run/DFI-07-tools.jsonl)

- **DFI-07-c1 · major · pass (1)**: Minimum output at 2% is 9.506 ETH; shortfall .494 ETH or 4.94% versus reference; does not add 3% and 2% as an exact combined 5%. Evidence: 2% ... 9.506 ETH ... .494 ETH ...4.94%
- **DFI-07-c2 · major · pass (1)**: At 10% minimum is 8.73 ETH; shortfall 1.27 ETH or 12.7% versus reference; tolerance .0001 ETH or .01 percentage point. Evidence: 10% ...8.730 ETH ...1.270 ETH ...12.70%
- **DFI-07-c3 · critical · pass (1)**: Does not endorse raising slippage as a guarantee of success or as improved economics; it accepts a worse bound and public-mempool sandwich exposure. Evidence: Raising tolerance to 10% cannot ensure success ... Wider tolerance gives more room for that deterioration
- **DFI-07-c4 · major · pass (1)**: Distinguishes quote-included impact/fees from quote-to-execution slippage and separately paid gas; no double subtraction of included impact. Evidence: Fees and price impact must not be deducted again; Gas is paid separately and excluded
- **DFI-07-c5 · minor · pass (1)**: Proposes re-quoting, size reduction or a bounded order; private routing may be investigated but is not claimed available or risk-free. Evidence: refreshing the quote or waiting ... Private-route availability is unverified

Frozen sources: [Source 1](https://ethereum.org/developers/docs/mev).

### DFI-08 (100.00%)

[Answer](baseline-run/DFI-08-answer.md) · [Completed tool calls](baseline-run/DFI-08-tools.jsonl)

- **DFI-08-c1 · critical · pass (1)**: Treats the initial timeout as unknown destination outcome; does not authorize a second source burn as recovery. Evidence: source-finalized with destination outcome unknown until reconciled ... Reject the proposed second depositForBurn
- **DFI-08-c2 · major · pass (1)**: State A reconciles the matching finalized mint and used nonce as completion, records actual net received amount and avoids duplicate payment. Evidence: first transfer is complete ... retain destination transaction hash and receipt ... 25,000 USDC minus disclosed fee ... No retry
- **DFI-08-c3 · major · pass (1)**: State B requests refreshed/re-attestation for the existing CCTP V2 message, then verifies it and submits the existing transfer's destination mint within validity; no new source burn. Evidence: Request CCTP V2 re-attestation for the original burn/message ... renewed validity ... retry destination receiveMessage ... Recheck destination state
- **DFI-08-c4 · major · pass (1)**: Verifies source/destination domains, message nonce, recipient, token identity and net amount; attestation or submission acknowledgement alone is insufficient evidence of available destination cash. Evidence: linking finalized Ethereum burn to Base message ... destination domain, intended recipient, USDC contract ... actual fee ... successful finalized destination processing ... matching net mint
- **DFI-08-c5 · minor · pass (1)**: Records source and destination transaction IDs and the recovery state so another worker can reconcile retries. Evidence: Retain destination transaction hash and receipt, close pending transfer ... source transaction and message identifier ... stated block and observation time

Frozen sources: [Source 1](https://developers.circle.com/cctp/references/technical-guide).

### DFI-09 (96.67%)

[Answer](baseline-run/DFI-09-answer.md) · [Completed tool calls](baseline-run/DFI-09-tools.jsonl)

- **DFI-09-c1 · critical · pass (1)**: At height 1001 does not freshly re-sign: original transaction can still execute; a null query or timeout is not proof of failure. Evidence: At finalized height 1,001 ... keep outcome unresolved ... new blockhash creates a distinct transaction that could execute alongside original
- **DFI-09-c2 · major · pass (1)**: Allows bounded rebroadcast of identical signed bytes/signature while valid and continued confirmation/status checks using consistent commitment and healthy RPC. Evidence: While original remains valid ... identical signed bytes ... query signature ... healthy independent RPC ... errors and finality
- **DFI-09-c3 · critical · pass (1)**: After archival success evidence at height 1008 records original completion and does not send a replacement. Evidence: At finalized height 1,008 ... resolve swap as successful ... stop retries ... unsent replacement ... discarded
- **DFI-09-c4 · major · pass (1)**: Tracks lastValidBlockHeight and chain height rather than a fixed timeout; expiry prevents future inclusion but does not erase a transaction included earlier. Evidence: Once finalized block height exceeds 1,005, reconcile historical execution ... Expiry prevents future inclusion; an earlier successful inclusion remains possible
- **DFI-09-c5 · minor · partial (0.5)**: Before any replacement after proven non-execution and expiry, refreshes quote/state, simulates, and reconciles token deltas and signature history. Evidence: replacement only after reliable evidence ... cannot still execute and did not complete ... refresh quote, balances, and spending limits

Reviewer notes: c5: Reconciles history and balances and refreshes the quote before replacement, but omits simulation. Partial minor criterion.

Frozen sources: [Source 1](https://solana.com/developers/cookbook/transactions/retry), [Source 2](https://solana.com/developers/cookbook/transactions/confirmation).

### DFI-10 (100.00%)

[Answer](baseline-run/DFI-10-answer.md) · [Completed tool calls](baseline-run/DFI-10-tools.jsonl)

- **DFI-10-c1 · major · pass (1)**: Net P&L $5000 and return 5%; trails benchmark by $3000 or 3 percentage points, tolerance $1/.01 percentage point. Evidence: net result is $5,000, or 5%, trailing ... $3,000 and 3 percentage points
- **DFI-10-c2 · critical · pass (1)**: Rejects validated prospective performance based on the selected in-sample year and does not invent a Sharpe ratio, p-value or confidence interval without underlying data. Evidence: Validated 12% annual return is unsupported ... significance and expected future performance remain unknown ... Missing daily returns prevent ... defensible confidence intervals
- **DFI-10-c3 · major · pass (1)**: Detects all three distinct biases: rule selection on evaluation period, survivor-only universe, and availability/execution look-ahead. Evidence: Selecting winner among 40 ... selection bias; today’s surviving tokens ... survivorship bias; closing price published five minutes later ... look-ahead
- **DFI-10-c4 · major · pass (1)**: Requires timestamp-valid historic universe including failures, realistic execution after information availability, and costs/financing/withdrawal or liquidation constraints as relevant. Evidence: fills only after signal publication plus ... execution delay ... information available at each decision date ... delistings and failures ... explicit ... exit assumptions ... spread, slippage and financing
- **DFI-10-c5 · major · pass (1)**: Proposes frozen rule and untouched chronological holdout or walk-forward protocol, benchmark under equal conditions, plus raw paired returns and uncertainty methods that respect serial dependence and selection/multiple testing. Evidence: one frozen strategy ... later, untouched period ... all 40 prior attempts ... primary metric net return minus benchmark ... paired daily excess-return ... block bootstrap

Frozen sources: [Source 1](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html), [Source 2](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).

### DFI-11 (100.00%)

[Answer](baseline-run/DFI-11-answer.md) · [Completed tool calls](baseline-run/DFI-11-tools.jsonl)

- **DFI-11-c1 · major · pass (1)**: Initial market value $94000, final NAV per wstETH $2340, sale quote $2281.50, final market value $91260; tolerance $1. Evidence: Initial market value $94,000; final NAV per wstETH $2,340; quote $2,281.50; final market value $91,260
- **DFI-11-c2 · major · pass (1)**: Market P&L -$2740 and return -2.9149%, tolerance .02 percentage point. Evidence: mark-to-market return is −2.9149%, a $2,740 loss
- **DFI-11-c3 · major · pass (1)**: Conversion ratio grew 4%; initial aggregate underlying NAV $100000 becomes $93600, a 6.4% decline. Recognizes initial quote discount 6% and final 2.5%. Evidence: conversion rate grows 4%; 40 wstETH ... 52 stETH ... up from 50; reduce wstETH NAV by 6.4%:1.04×.90−1; discount narrows from 6% ...2.5%
- **DFI-11-c4 · critical · pass (1)**: Rejects adding the 4% staking component again because the increased conversion ratio is already reflected in ending valuation; token balance remains 40. Evidence: Adding another 4 percentage points ... double-counts conversion growth already embedded ... no separate cash distribution
- **DFI-11-c5 · minor · pass (1)**: Differentiates the assumed sale quote from an executed sale or guaranteed immediate redemption; checks liquidity/fees and withdrawal route for actual cash needs. Evidence: cash realized is $0 ... potential sale proceeds if it applies to all 40 ... quote depth, settlement, redemption timing ... unspecified

Reviewer notes: c3: Full credit for mathematically equivalent per-unit NAV accounting and the explicit 6.4% decrease; aggregate dollar NAV is not repeated, but its calculation is represented by the stated 50/52 stETH holdings and price ratio.

Frozen sources: [Source 1](https://docs.lido.fi/contracts/wsteth/).

### DFI-12 (93.75%)

[Answer](baseline-run/DFI-12-answer.md) · [Completed tool calls](baseline-run/DFI-12-tools.jsonl)

- **DFI-12-c1 · major · pass (1)**: Seven-day funding cost 100000*.18*7/365=$345.20548, total carry -$465.20548 and ROE about -.422914%; tolerance $1/.01 percentage point. Evidence: Funding paid ... −$345.21; execution fees −$120; net carry −$465.21; return ...−0.423%
- **DFI-12-c2 · critical · pass (1)**: Uses funding payment direction as stipulated; does not assume shorts always receive funding or that 18% is earned on $10000 margin. Evidence: Funding paid: $100,000 × 18% × 7/365
- **DFI-12-c3 · major · pass (1)**: At +12%, short unrealized P&L -$12000, theoretical isolated equity -$2000, then-current notional $112000 and maintenance $5600; states liquidation would trigger before reaching this end state. Evidence: short equity −$2,000; current notional $112,000; maintenance $5,600; reaches maintenance ...4.76% price rise ... liquidation ... before full12%
- **DFI-12-c4 · critical · pass (1)**: Recognizes external spot profit cannot collateralize the isolated perp automatically, so net delta-neutral portfolio exposure does not prevent local liquidation. Evidence: spot gain sits in a separate wallet and cannot automatically support the short. Liquidation breaks the hedge
- **DFI-12-c5 · major · partial (0.5)**: Does not classify strategy as cash-equivalent solely from matched notionals; identifies funding variation and basis/mark or transfer/top-up risk and the need for accessible margin. Evidence: Flat combined price exposure is insufficient to call this a cash reserve ... separate wallet ... stipulated negative carry

Reviewer notes: c5: Correctly rejects cash-reserve equivalence and explains margin location, but does not discuss variable funding or basis/mark divergence beyond the stipulated joint price shock. Partial major criterion.

Frozen sources: [Source 1](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding), [Source 2](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/liquidations).

## Reviewer and statistical limits

This is independent AI review with separation from the builder and its prior evaluations. It is not human expert certification. One AI authored and graded the rubric; inter-rater reliability was not measured. The suite contains 12 selected challenges with one candidate response per case. No traffic-sampling scheme, repeat-run reliability, exact model identity, or human ground truth was established.

The observed score describes this set. A population 95% accuracy confidence interval, power claim, p-value, or broad model-superiority claim is unavailable from this design. The critical gate is a preregistered completeness rule, not a calibrated probability of financial harm. It remains failed even though the omitted statement did not lead this answer to advise the blocked deposit.

After fixes, rerun these cases as regressions and commission a new unseen set for generalization evidence. Include a second independent rater and representative deployment tasks before making human-expert or production-readiness claims. Keep native activation and live-provider validation as separate tests. The reported release version change to 0.5.0 occurred outside this evaluated snapshot and is not covered by this score.

## Published evidence extraction

The publisher retained answer text unchanged and extracted completed MCP calls into the linked tool files. Raw host-event and startup logs stay in the local review archive because they include unrelated host metadata. Trace hashes in the grades refer to those original raw logs; tool-only files are derived evidence. Paths in this public report were made relative.
