**The fixture produces a seven-day loss of $311.51, or −0.3115% on $100,000 committed equity.** This assumes both legs remain open through the period.

| Component | Calculation | P&L |
|---|---|---:|
| Spot and perpetual price P&L | Both finish at starting prices | $0.00 |
| Funding received | $80,000 × 12% × 3/365 | +$78.90 |
| Funding paid | $80,000 × 24% × 4/365 | −$210.41 |
| Execution fees | Given | −$180.00 |
| **Net** | Calculated before rounding | **−$311.51** |

Return on committed equity = −$311.50685 ÷ $100,000 × 100 = **−0.3115%**.

The founder should reserve the $500 separately. This fixture generates a loss, so paying the bill would consume principal. The combined position has approximately zero opening delta; negative delta describes the short leg. Delta measures price sensitivity and provides no promise about cashflow.

Two independent failure mechanisms are:

1. **Funding reverses.** The supplied schedule already turns funding into a net $131.51 expense before fees. These rates are scenario assumptions. Future funding can change magnitude or sign even when the price hedge holds.

2. **The isolated short can be liquidated during an interim ETH rally.** Spot gains do not automatically replenish its separate margin. Liquidation becomes possible when margin equity falls below the venue’s maintenance requirement. A 25% rise would create a $20,000 short loss before funding and fees; maintenance requirements can trigger liquidation earlier. The exact threshold is unknown because venue rules and collateral details are missing. A later return to the starting price would not restore a liquidated hedge.

Paying from committed capital also requires releasing collateral or unwinding positions and withdrawing spendable funds. Withdrawal availability and timing are unspecified.

Conceptual support: Scout’s curated [perpetuals and basis reference](https://github.com/emlai/defi-native-skill/blob/902734ad83f387cc7e4d84815ae655efce162d43/references/concepts.md), reviewed September 10, 2026. All figures above come solely from your hypothetical fixture.