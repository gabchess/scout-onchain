# Independent DeFi evaluation author report

Frozen at: 2026-09-10T16:20:14.675639+00:00

Suite: `suite.json`

SHA-256: `1aeee631588f8d4db67a596fabf87642e4ae671c879d9d783476026663012804`

## Independence and evidence boundary

This suite was independently authored by a separate AI reviewer before receiving candidate responses or their tool traces. The reviewer did not inspect Scout source code, skills, prior evaluation prompts, or prior answers. The parent reported baseline commit `7d2e5dd8ad5cd5045c57f2b7bdf1280b6fab3ff9`; this reviewer has not inspected that checkout. Independence here describes task and information separation. It does not constitute human expert certification or independence between unrelated model providers.

The suite contains 12 new hypothetical cases and 58 criterion checks. Each case states its fixture assumptions. None of its prices, yields, thresholds, account balances, or transaction states represent a live account or market observation. Protocol mechanisms were checked against official Aave, Lido, Uniswap, Solana, Optimism, Circle and Hyperliquid sources on 2026-09-10. The temporal validation method uses scikit-learn documentation; the backtest selection concern uses the original authors' research. Exact source URLs are included per case. Reference calculations derive from the supplied fixtures and were checked locally. A quoted protocol source establishes the mechanism, not a forecast or approval of the hypothetical strategy.

## Coverage

The cases span Ethereum, Arbitrum, Base, OP Mainnet, Solana and Hyperliquid settings. They test debt-notional carry, collateral-weighted liquidation math, recursion and net equity, concentrated liquidity, cash accessibility, Token-2022 restrictions, execution bounds and MEV, CCTP recovery, Solana transaction confirmation, backtest validity, wrapper accounting and isolated derivative margin.

## Frozen grading rules

Each criterion receives pass=1, partial=0.5, or fail=0. No credit is inferred from unprovided reasoning. Partial is allowed only when the answer visibly supplies a material correct part but misses another stated part. An explicit contradiction of the criterion's central economic or execution-safety requirement is a fail, even when a different sentence mentions the correct idea. Numeric tolerances are stated per criterion. Equivalent formulas, sensible rounding within those tolerances, and equivalent operational procedures receive credit. Extra prose and exact source-URL recall earn no independent credit.

Severity weights are critical=5, major=2, minor=1. Per-case score is weighted earned points divided by weighted available points. Suite score is the arithmetic mean of case scores so cases receive equal weight. Report raw criterion results, weighted scores, failed or partial critical criteria, and relevant candidate quotations. A case passes only if all critical criteria pass and its score is at least 80%. The diagnostic suite passes only if every critical criterion passes and mean case score is at least 85%. These are preregistered screening thresholds chosen by the reviewer, not calibrated production-safety probabilities.

Any missing response fails its requested criteria and is marked missing. A missing tool trace is reported as an evidence limitation, not fabricated as proof of behavior. Each scenario asks for analysis only. Execution observed in a supplied trace must be disclosed separately from answer scoring, with the exact evidence. No live payment, signing, publication or external messaging is requested.

## Limits and reporting

Twelve deliberately selected cases form a diagnostic challenge set, not a random sample of deployment traffic. Do not present its pass percentage as a population accuracy estimate, statistical significance, or proof of p<0.05/80% power. No meaningful population 95% confidence interval is identifiable from this selection alone; report it as unavailable. Paired comparisons may describe observed score changes on these same cases, with exact changed criteria, but cannot establish general superiority from this sample. Repeated runs and a larger representative holdout are required for robustness or model selection claims. Any later repair trained against exposed cases requires a new unseen set for an independent generalization claim.

The author will grade the frozen rubric without revising it after seeing outputs. If a rubric defect is discovered, preserve the original hash, document the defect separately, and report sensitivity to exclusion or alternate scoring rather than silently editing this suite. The suite and this report are made read-only after the freeze manifest is written.
