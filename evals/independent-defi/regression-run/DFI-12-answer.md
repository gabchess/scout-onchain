**Seven-day net carry is −$465.21, a −0.423% return on $110,000**, assuming a 365-day year, unchanged ending prices, and a surviving hedge. All numbers below use your fixtures.

| Component | Calculation | Result |
|---|---|---:|
| Funding paid by short | −$100,000 × 18% × 7/365 | −$345.21 |
| Opening/closing fees | | −$120.00 |
| Net carry | −$345.21 − $120 | **−$465.21** |
| Committed-equity return | −$465.21 / $110,000 | **−0.423%** |

Ending equity would be **$109,534.79**. Funding is fixed by this hypothetical schedule; future market funding can change magnitude or sign.

For the separate **12% intraday rise**, before funding or fees:

| Measure | Calculation | Result |
|---|---|---:|
| Spot gain | $100,000 × 12% | +$12,000 |
| Short price PnL | −$100,000 × 12% | −$12,000 |
| Isolated short equity | $10,000 − $12,000 | **−$2,000** |
| Current perp notional | $100,000 × 1.12 | $112,000 |
| Maintenance requirement | $112,000 × 5% | **$5,600** |
| Maintenance shortfall | $5,600 − (−$2,000) | **$7,600** |

Under the stipulated maintenance test, liquidation eligibility arises when isolated equity falls below maintenance. For a price rise \(r\):

\[
10{,}000-100{,}000r < 0.05(100{,}000)(1+r)
\]

The equality boundary is **a 4.762% rise**. A continuous move to 12% crosses it well beforehand. The −$2,000 is a hypothetical mark-to-market value for an unclosed short; actual liquidation timing, fills, and any deficit treatment remain unspecified.

**Flat combined price exposure is insufficient to call this a cash reserve.** The spot gain sits in a separate Ethereum wallet and cannot automatically support isolated margin. Liquidation can break the hedge, leaving directional ETH exposure even if prices later return to their starting point.

Accessing cash requires closing the short, selling spot, and withdrawing or transferring proceeds. Exit liquidity and transfer delays are unspecified. Scout’s curated [basis and perpetuals reference](https://github.com/emlai/defi-native-skill/blob/902734ad83f387cc7e4d84815ae655efce162d43/references/concepts.md), reviewed September 10, 2026, supports these conceptual risks; live Hyperliquid rules were not checked.