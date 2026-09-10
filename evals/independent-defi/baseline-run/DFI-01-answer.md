**Annual profit is $1,310 at 9% borrowing APR, yielding 2.62% on your original equity. At 13%, profit falls to $110, or 0.22%.** These results use your stipulated fixtures and simple interest.

Original equity is $50,000: $50,000 collateral + $30,000 vault assets − $30,000 debt.

| Annual component | 9% borrowing APR | 13% borrowing APR |
|---|---:|---:|
| Staking: $50,000 × 4% | +$2,000 | +$2,000 |
| Vault: $30,000 × 7% | +$2,100 | +$2,100 |
| Realized incentives: $30,000 × 1% × 50% | +$150 | +$150 |
| Borrow interest | −$2,700 | −$3,900 |
| Execution costs | −$240 | −$240 |
| **Net annual P&L** | **+$1,310** | **+$110** |
| **Return on $50,000 equity** | **2.62%** | **0.22%** |

For borrowing APR \(b\), expressed as a decimal:

\[
\text{P&L}=2{,}000+2{,}100+150-240-30{,}000b
\]

Setting P&L to zero gives **13.3667% borrowing APR**.

The financed vault leg, including incentives and execution costs, loses $690 at 9% and $1,890 at 13%. Staking income covers those losses. If incentives disappear, total P&L becomes $1,160 and −$40, respectively.

The calculations leave out several material risks:

- **Collateral price and liquidation:** Falling ETH prices or a wstETH discount can trigger liquidation. Initial debt equals 60% of collateral value, but liquidation distance remains unknown without the protocol’s oracle and liquidation parameters.
- **Changing yields:** Borrowing costs can rise while staking income, vault returns or rewards fall.
- **Exit liquidity:** Vault withdrawal delays could prevent timely debt repayment. Slippage and gas spikes may exceed the $240 allowance.
- **Asset and protocol losses:** USDC can depeg or face issuer restrictions. Staking penalties, smart-contract exploits and vault allocation losses can reduce principal.

Scout’s [curated lending concepts](https://github.com/emlai/defi-native-skill/blob/902734ad83f387cc7e4d84815ae655efce162d43/references/concepts.md), reviewed September 10, 2026, support the conceptual risk discussion; no live protocol state was verified.