**Exclude this deposit from executable treasury allocations: the simulated hook denies the vault transfer.** If both transfers succeeded, the vault would receive **9,800 spendable tokens**.

Using your stipulated fixtures, 150 basis points equals 1.5%, and the 100-token cap applies separately to each transfer:

| Transfer | Amount sent | Fee calculation | Spendable received |
|---|---:|---:|---:|
| Wallet → intermediate | 10,000 | min(150, 100) = 100 | 9,900 |
| Intermediate → vault | 9,900 | min(148.5, 100) = 100 | 9,800 |

Six decimals introduce no rounding here. Withheld fees cannot be forwarded as spendable tokens.

The denied transfer delivers **zero tokens to the vault**. Simulation changes no account state. If attempted within one atomic transaction, the failure would roll back both transfers. If the first transfer had committed in a separate transaction, 9,900 spendable tokens would remain at the intermediate account; recovery would depend on its authority and hook permissions.

Before reconsidering the allocation, check:

- **Identity and claim:** exact mint address, Token-2022 program ownership, issuer, and any enforceable redemption rights. The symbol “USDC” establishes neither identity nor dollar value.
- **Mint controls:** active and scheduled fee settings, fee configuration and withdrawal authorities, mint/freeze authorities, and other enabled extensions. The issuer’s permanent delegate can transfer or burn tokens across this mint’s accounts. An individual holder cannot revoke that authority.
- **Route accounts:** each account’s mint, token program, controlling authority, initialized/frozen status, spendable balance, withheld fees, and ordinary delegate permissions. Verify who can recover funds from the intermediate account.
- **Hook and vault compatibility:** hook program and upgrade/control authorities, required extra accounts, the precise denial reason, and permission conditions for every transfer. Confirm vault accounting credits the net received amount and supports these extensions.
- **Exit:** whether vault redemption and a return transfer can pass the hook, who can change those permissions, and any withdrawal queue or delay. Those facts remain unknown.

Reconsider only after the denial is resolved and the complete deposit and exit paths are validated. No yield or fixed cashflow is supplied.

Source status: calculations use your hypothetical fixtures. Scout’s curated conceptual cards were reviewed September 10, 2026; no live account state was checked. See [Solana’s permanent-delegate documentation](https://solana.com/docs/tokens/extensions/permanent-delegate).