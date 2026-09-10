**The fee-only result is 9,800 spendable tokens. The hook denial makes the deposit non-executable under the stipulated state.**

Each transfer charges `min(amount × 0.015, 100 tokens)`:

| Transfer | Sent | Fee withheld | Spendable received |
|---|---:|---:|---:|
| Wallet → intermediate | 10,000 | 100 | 9,900 |
| Intermediate → vault | 9,900 | 100 | 9,800 |

Six decimals means the hypothetical final amount is **9,800,000,000 base units**. Both fees hit the cap, so rounding has no effect. The intermediate account’s withheld 100 tokens cannot fund its onward transfer.

With the hook rejecting the vault transfer, **the vault receives zero from this route**. Simulation itself changes no balances. If both legs were submitted in one atomic transaction, failure would roll back both transfers. If submitted separately and the first succeeded, 9,900 spendable tokens would remain in the intermediate account after the second failed.

Exclude this deposit from executable treasury allocations. The “USDC” symbol establishes neither the mint’s identity nor its redemption rights or dollar value. The issuer’s permanent delegate can transfer or burn tokens held in accounts for this mint, creating material issuer control over treasury holdings.

Check these facts before reconsidering:

- **Mint identity and configuration:** exact mint address, Token-2022 program ownership, decimals, all extensions, active and scheduled fee settings, mint/freeze authorities, fee configuration and withdrawal authorities, and permanent delegate.
- **Route accounts:** source, intermediate and vault token-account addresses; matching mint and token program; account authorities, delegates, frozen state, spendable balances and withheld fees. Verify who can recover funds from the intermediate account.
- **Hook requirements:** hook program, upgrade/control authorities, required extra accounts and permissions, and the precise denial reason. Confirm vault support for these extensions and its withdrawal path.
- **Economic claim:** authenticated issuer evidence, backing and redemption terms, plus exit liquidity at the intended size. These remain unknown.

All amounts and states above come from your fixtures. Scout’s curated conceptual cards, reviewed September 10, 2026, reference the [Solana Foundation developer material](https://github.com/solana-foundation/solana-dev-skill/tree/69935cfc19298b7db6e6f7471f56ff79369214da); no live account verification or transaction occurred.