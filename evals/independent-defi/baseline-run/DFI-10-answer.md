**The reported net result is $5,000, or 5%, trailing the benchmark by $3,000 and 3 percentage points.** All figures below use your stipulated fixtures.

| One-year result | Dollars | Return on $100,000 |
|---|---:|---:|
| Gross P&L | $12,000 | 12% |
| Recorded costs | −$7,000 | −7% |
| Net P&L | $5,000 | 5% |
| Passive benchmark, after costs | $8,000 | 8% |
| Net result minus benchmark | −$3,000 | −3 percentage points |

With fixed capital and no compounding, these are simple one-year returns.

“Validated 12% annual return” is unsupported. The defensible statement is: **“The selected rule reported 12% gross and 5% after recorded costs in one historical year under the stated simulation assumptions.”** Even that result has material biases:

- Selecting the winner among 40 rules on the evaluation year introduces selection bias. That year is development data.
- Using today’s surviving tokens introduces survivorship bias and future information into historical eligibility.
- Filling at a closing price published five minutes later introduces look-ahead bias. The assumed fill precedes signal availability.
- Missing daily returns prevent calculation of drawdown, volatility, risk-adjusted performance and defensible confidence intervals. Failed-token losses cannot be reconstructed from the retained evidence.

The arithmetic establishes reported benchmark underperformance. Achievable returns, statistical significance and expected future performance remain unknown.

The smallest credible next validation is **one frozen strategy evaluated once on a later, untouched period**:

1. **Lock the protocol before testing.** Record the selected rule, all 40 prior attempts, capital assumptions, benchmark, cost model and primary metric: net return minus benchmark return. Precommit the test horizon and evaluation date. Choose duration around a stated economically meaningful advantage and desired precision; the retained totals cannot establish a sufficient sample size.
2. **Repair information timing and eligibility.** Permit simulated fills only after signal publication plus a declared execution delay, using available prices and liquidity. Determine token eligibility from information available at each decision date. Retain delistings and failures, with explicit valuation and exit assumptions.
3. **Use later data.** Reserve an untouched chronological holdout, or collect a prospective shadow record if none exists. Keep development outcomes from overlapping the test window. Any tuning after inspection requires another untouched period.
4. **Retain an auditable record.** Save daily portfolio and benchmark returns, timestamped inputs, simulated fills, holdings and itemized costs. Model spread, slippage and financing at the stated $100,000 scale.
5. **Report uncertainty.** Show cumulative net return, benchmark difference, maximum drawdown, dates, observation count and trade count. Estimate an interval for the paired daily excess-return series using a method that preserves serial dependence, such as a block bootstrap. Disclose interval assumptions and limited sample size. Include sensitivity to higher costs and execution delays.

A favorable holdout would provide out-of-sample simulation evidence. Claims about a repeatable annual return would still require evidence across further periods.

Methodology source: Scout’s curated [backtest-validity reference](https://github.com/gabchess/Vibe-Trading/blob/ff6695912c1d6b7b8405bcd0e0f9b99ae7893e41/agent/SKILL.md), reviewed September 10, 2026; conceptual guidance.