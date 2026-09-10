**Usable tomorrow: $14,591.40. Shortfall: $5,408.60.** These calculations use only your stipulated fixtures.

| Asset | Usable for tomorrow’s payment |
|---|---:|
| Ethereum cash after gas reserve: $8,000 − $200 | $7,800.00 |
| U sale: 7,000 × $0.98 × 0.99 | $6,791.40 |
| Arbitrum lending claims | $0.00 |
| OP Mainnet withdrawal | $0.00 |
| **Total** | **$14,591.40** |

The shortfall is **$20,000 − $14,591.40 = $5,408.60**.

The $2,000 withdrawable on Arbitrum remains on that chain, with no stipulated route that reaches Ethereum before the deadline. The remaining $8,000 is unavailable for withdrawal.

The OP withdrawal requires proving, completion of the fault-challenge period, and L1 finalization before proceeds become usable. Initiation today does not make the $15,000 available tomorrow. This mechanism comes from Scout’s curated conceptual card, reviewed September 10, 2026, referencing the [OP Stack withdrawal specification](https://specs.optimism.io/protocol/withdrawals.html); no live parameters were checked.

Headline holdings obscure the payment’s chain and timing requirements. U also produces less than face value after its discount and execution haircut. Even after selling it under the fixture, the treasury cannot fully settle tomorrow’s obligation.

A practical reserve policy is to hold **100% of upcoming obligations in immediately spendable, payment-compatible assets on the settlement chain**, plus a separate gas reserve and operating buffer. For this deadline, the minimum would be **$20,200 before an additional buffer**. Set the reserve horizon to cover the longest stressed exit time of assets funding payments, including bridge finalization and an operational margin. Review coverage daily; any drop below that floor triggers replenishment and suspension of new yield allocations. Count pending bridges and lending claims toward reserves only once their proceeds are spendable on Ethereum.