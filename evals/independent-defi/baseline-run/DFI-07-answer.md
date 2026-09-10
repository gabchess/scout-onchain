**The 2% minimum is 9.506 ETH, a 4.94% output shortfall versus the independent reference.** All calculations use your stipulated fixtures.

Minimum output = quoted output × (1 − slippage tolerance).

| Tolerance | Minimum output | Shortfall versus 10 ETH | Shortfall % |
|---|---:|---:|---:|
| 2% | 9.70 × 0.98 = **9.506 ETH** | **0.494 ETH** | **4.94%** |
| 10% | 9.70 × 0.90 = **8.730 ETH** | **1.270 ETH** | **12.70%** |

The quote already falls 0.30 ETH, or 3%, below the reference. At 2% tolerance, another 0.194 ETH is permitted: 0.30 + 0.194 = 0.494 ETH. Fees and price impact must not be deducted again.

**Raising tolerance to 10% cannot ensure success.** It permits an additional 0.776 ETH of output deterioration compared with the 2% minimum.

- **Price impact** comes from the trade’s size relative to pool liquidity. It is already included in the quote alongside pool fees; their individual contributions are unspecified.
- **Slippage** measures execution’s departure from the quote. The tolerance sets the permitted downside; execution could still fall below that bound and revert.
- **Gas** is paid separately and excluded from these output shortfalls. Wider tolerance does not fix congestion or inadequate gas pricing. A reverted onchain transaction can still consume gas.
- **Sandwich risk** arises when an attacker trades before and after the visible swap, worsening its execution for profit. Wider tolerance gives more room for that deterioration; an attack’s profitability remains unknown.

During a public-mempool spike, refreshing the quote or waiting provides a basis for reassessing acceptable output. Any wider tolerance should follow an explicit willingness to accept its minimum. Private-route availability is unverified, so it cannot support this proposal.

Concepts checked against Scout-curated cards reviewed September 10, 2026, citing [ETH Skills](https://github.com/austintgriffith/ethskills/tree/06ea4efa08076ff04f6ca4945ef4a2ca881115b0). These are conceptual sources. No transactions were executed.