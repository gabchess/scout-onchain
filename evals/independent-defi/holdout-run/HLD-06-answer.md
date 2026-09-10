This transfer contributes **0 USDC to Y’s available treasury cash**. Recording 14,940 USDC as available cash would overstate the treasury’s balance.

Under the supplied hypothetical evidence:

| Evidence | What it proves |
|---|---|
| Finalized Ethereum burn | 15,000 USDC was burned on the source chain. |
| Valid attestation | The message was attested. This does not establish that its recipient matched the treasury’s intent. |
| Used destination nonce | The message’s nonce has been consumed, preventing another mint through replay of that message. |
| Successful finalized Base receipt | The destination transaction succeeded and finalized. |
| Decoded message and mint event naming X | The transfer minted 14,940 USDC to X, outside treasury control. |
| No credit to Y | The intended treasury recipient received nothing from this transfer. |

The reconciliation is **15,000 = 14,940 delivered to X + 60 fee**. The evidence establishes completed delivery to the wrong recipient. It provides no basis for treating X’s balance as treasury cash.

Record the source outflow and fee, and flag the 14,940 USDC as a misdirected amount. Whether it qualifies as a recovery receivable requires evidence supporting a claim and collectibility; otherwise, assess loss recognition under the applicable accounting policy.

Reject the proposed second burn. It would create another 15,000 USDC outflow and would not reverse the first transfer. Dashboard correction requires correcting the accounting.

Recovery depends on whoever controls X returning the funds or an independently established recovery process. The fixture establishes no treasury power to revoke or redirect the finalized mint, and the consumed nonce prevents reusing the attestation to mint to Y. Recovery authority, timing, and collectibility remain unknown.