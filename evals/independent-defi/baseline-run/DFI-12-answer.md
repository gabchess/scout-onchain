Using your fixtures and a **365-day year**, with unchanged ending prices and a surviving hedge:

| Seven-day result | Calculation | Amount |
|---|---|---:|
| Funding paid | $100,000 × 18% × 7/365 | −$345.21 |
| Execution fees | Opening and closing combined | −$120.00 |
| Net carry | Funding plus fees | **−$465.21** |
| Return on committed equity | −$465.21 / $110,000 | **−0.423%** |

Ending equity is **$109,534.79**.

For the separate **12% intraday rise**, before funding or fees:

| Stress measure | Calculation | Result |
|---|---|---:|
| Spot gain | $100,000 × 12% | +$12,000 |
| Linear short loss | −$100,000 × 12% | −$12,000 |
| Isolated short equity | $10,000 − $12,000 | **−$2,000** |
| Current perp notional | $100,000 × 1.12 | $112,000 |
| Maintenance requirement | $112,000 × 5% | **$5,600** |

The isolated account is **$7,600 below maintenance** at that hypothetical mark. It reaches maintenance much earlier: solving  
$10,000 − $100,000r = 5% × $100,000(1+r)  
gives a **4.76% price rise**. Liquidation could therefore occur before the full 12% move. The −$2,000 figure assumes the short remains open; actual liquidation timing and proceeds are unspecified.

**Flat combined price exposure is insufficient to call this a cash reserve.** The spot gain sits in a separate wallet and cannot automatically support the short. Liquidation breaks the hedge, leaving the treasury exposed to ETH price movements. Even a surviving hedge incurs the stipulated negative carry.

[Scout’s curated conceptual source](https://github.com/emlai/defi-native-skill/blob/902734ad83f387cc7e4d84815ae655efce162d43/references/concepts.md), reviewed September 10, 2026, supports this margin-location distinction. All numerical results above use your fixtures.