**No. At finalized height 1,001, the agent should keep the outcome unresolved.** The original transaction’s last valid height is 1,005. A timeout and temporary null lookup cannot establish failure. Signing with a new blockhash creates a distinct transaction that could execute alongside the original, spending another 8,000 USDC.

A safe hypothetical retry sequence is:

1. Preserve the original signed bytes, signature, blockhash B, last valid height, and swap intent. Block concurrent replacement attempts.
2. Query the signature with transaction-history search enabled. Use a healthy independent RPC or archival source when coverage is uncertain. Check transaction errors and finality.
3. While the original remains valid, any rebroadcast should use **the identical signed bytes**. This retains its signature and transaction identity.
4. Once finalized block height exceeds 1,005, reconcile historical execution and token changes. Expiry prevents future inclusion; an earlier successful inclusion remains possible.
5. Consider a replacement only after reliable evidence establishes that the original cannot still execute and did not complete the swap. If history remains inconclusive, keep the operation unresolved. Before any separately authorized replacement, refresh the quote, balances, and spending limits.

**At finalized height 1,008, the stipulated archival proof and matching token deltas resolve the swap as successful.** Record the original signature and execution details, reconcile balances, and stop retries. Any unsent replacement should be discarded. If a replacement was already broadcast, track it separately because the original’s success cannot cancel it.

Wall-clock time cannot reliably determine expiry because block production and RPC visibility vary. Checking whether B is expired now also leaves the historical outcome unanswered: the swap could have executed before expiry, as it did here.

Source: Scout’s curated “Recent blockhash expiry” card, reviewed September 10, 2026, citing [Solana Foundation developer guidance](https://github.com/solana-foundation/solana-dev-skill/tree/69935cfc19298b7db6e6f7471f56ff79369214da). This is conceptual guidance applied to your fixtures; no live observations or transactions were made.