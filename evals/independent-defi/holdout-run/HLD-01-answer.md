The required gross transfer is **8,030.000000 tokens**, using your hypothetical fee settings.

| Calculation | Tokens |
|---|---:|
| Uncapped fee: 8,030 × 0.0075 | 60.225000 |
| Fee after applying the cap | 30.000000 |
| Supplier’s spendable receipt | **8,000.000000** |

With six decimals, that is **8,030,000,000 base units** transferred, with 30,000,000 withheld as fees. The cap applies from 4,000 tokens onward; rounding does not affect this result. Withheld fees are unavailable for the supplier to spend.

**The “issuer-proof” claim is false under this fixture.** K’s permanent-delegate authority lets it transfer or burn tokens from accounts belonging to this mint, including the treasury’s and supplier’s accounts. Revoking ordinary account delegates leaves that authority intact. Moving tokens to another account for the same mint preserves K’s reach.

Under standard Token-2022 rules, **the current permanent delegate, K, can change that authority or disable it by setting it to `None` through `SetAuthority` for `PermanentDelegate`.** The treasury owner cannot remove it. Holding the mint authority alone does not grant that power. Disabling it is irreversible under those rules.

I would defer recommending this mint for next month’s payroll. Evidence that would change that assessment includes:

- Finalized mint state showing the permanent delegate disabled, supported by the authority-change transaction. Rotation to another controller retains the power.
- Verified remaining controls, including freeze authority, transfer hooks and fee-setting authority, plus any scheduled fee changes.
- Evidence of backing and enforceable redemption rights, where applicable, together with liquidity at payroll size and settlement timing before payroll is due. Exit fees, queues and restrictions remain unknown.

The calculation fixes the supplier’s receipt under the supplied settings. Future spendability remains exposed to K’s authority.

Source status: Scout’s curated [Token-2022 reference](https://solana.com/docs/tokens/extensions/permanent-delegate) supports the authority distinction. Its imported community glossary is unverified and contains a conflicting “cannot be changed” claim. No live documentation or account state was checked, and no action was executed.