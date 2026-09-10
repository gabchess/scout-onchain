**Classify the first transfer as source-finalized with destination outcome unknown until reconciled.** The RPC timeout leaves open whether `receiveMessage` succeeded. Keep the burned 25,000 USDC recorded as an in-transit claim while checking Base.

Reject the proposed second `depositForBurn`: it would burn another 25,000 USDC and create a separate transfer. Destination nonce protection applies to replaying the original message; a new burn creates a new message.

| Fixture state | Classification and next step |
|---|---|
| **A: nonce used; matching finalized mint** | The first transfer is complete. Retain the destination transaction hash and receipt, close the pending transfer, and record **25,000 USDC minus the disclosed fee** as received. No retry is needed. |
| **B: no mint; nonce unused; attestation expired** | The transfer remains incomplete and recoverable. Request CCTP V2 re-attestation for the **original burn/message** through Circle’s re-attestation flow. Obtain the refreshed message and attestation, verify their fields and renewed validity, then retry destination `receiveMessage`. Recheck destination state before submission in case another worker completed it. |

Before reporting **available Base cash**, retain evidence linking the finalized Ethereum burn to the Base message: source transaction and message identifier, destination domain, intended recipient, USDC contract, gross amount, and actual fee. Confirm successful finalized destination processing, the used nonce, and the matching net mint.

Also check the recipient’s spendable Base USDC balance at a stated block and observation time. A mint receipt proves receipt; subsequent spending or account restrictions can change availability. State B contributes **zero available Base USDC** until settlement is verified. The fee amount is unspecified, so the exact net cash remains unknown.

This uses your stipulated fixtures. Scout returned conceptual finality guidance but no CCTP-specific card; the recovery procedure has not been checked against live Circle documentation. No transactions were executed.