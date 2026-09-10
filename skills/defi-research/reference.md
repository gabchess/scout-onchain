# Scout research playbooks

These are original analysis procedures. Source concepts are indexed in the bundled knowledge cards and `docs/knowledge/SOURCE-LOCK.json`. They do not create action authority.

## Portfolio review

Start with goal, horizon and cash needs. Name the observed wallet scope and timestamp. Calculate gross weights, HHI, effective position count and a declared shock using `get_portfolio_risk`. Show the dollar effect so the user can judge its relevance. State that the scenario applies uniformly and is not a forecast.

Next, map economic exposures where data permits. Separate supplied collateral, borrow liabilities, wrapper claims and spendable balances. Assess issuer, venue, chain, bridge and exit dependence. When the source only supplies asset labels, mark look-through, net exposure and correlations unknown. Do not turn an incomplete balance sheet into a suitability judgment.

Discuss a rebalance as a conditional proposal: what risk it would reduce, costs it would incur and which observations would invalidate it. Do not invent target percentages for a user who has not supplied constraints.

## A quoted vault yield

Record the exact asset claim and protocol at a dated source. Who controls allocation? What is collateral? Who owes the return? Who absorbs first loss? Identify authority changes and delays.

Use a table to separate base interest, incentives, borrowing expense, protocol fees and entry/exit costs. Rates must use the same convention. `assess_defi_yield` models simple APR applied to the same supplied principal; actual leveraged debt requires a separate debt notional calculation. Do not feed advertised APY into its APR input without a stated conversion.

Compare a base scenario with incentives removed, financing costs raised and redemption delayed. A negative outcome can come from price movement even when token-unit yield is positive. Inspect the exit path at the user's trade size, including withdrawal queues, bridge return paths and destination gas.

## A lending position

Obtain supplied collateral, debt including accrued interest, oracle price, liquidation threshold, liquidation bonus and relevant market mode. Show net equity as supplied collateral minus debt, while keeping the collateral and debt amounts visible. Use the protocol's own health-factor formula. A multi-asset position requires each adjusted collateral contribution. A liquidation warning needs those inputs and a timestamp; the gross holdings shock tool cannot supply them.

Check utilization and rate changes along with price risk. An apparently profitable loop can fail when financing cost rises or collateral liquidity falls. Match withdrawal expectations with available liquidity.

## An LP position

Identify pool, token contracts or mints, fee tier, range, share and current tick. For an advertised LP rate, explain that a concentrated position can stop earning swap fees outside its range even when the pool headline rate stays high. Explain which asset exposure develops when price leaves the range. Compare resulting value against holding the starting inventory over the same period. Add earned fees and incentives, then subtract entry, rebalance and exit costs.

The common constant-product impermanent-loss expression `2*sqrt(r)/(1+r)-1` is a toy relative-price comparison for a full-range equal-value two-asset pool without fees. It does not price a concentrated position, a multi-asset pool or every path-dependent strategy. Use protocol-specific position data for those cases.

## A trading idea

Write thesis, expected horizon, observable trigger, invalidation and allowed loss before selecting size. Distinguish missing information from a reason to transact. Evaluate spread, depth, financing, fees and likely slippage at the proposed size. Check correlated exposure already held.

Backtests need time-ordered data, held-out periods, realistic fills, costs, survivorship treatment and a record of how many strategies were tried. Report maximum drawdown and sample size alongside returns. Paper and shadow runs are simulation evidence. A strong result earns another test; it does not authorize a trade or prove future return.

## Action and uncertain outcomes

Name a supported operation only when the user identifies one. `plan_zerion_action.action` is an enum: swap, bridge, stake, transfer, payment, data_access. A request to start an unspecified strategy needs clarification before choosing an operation.

Scout x402 is restricted to configured Zerion analytics. It cannot pay an arbitrary research merchant. State this scope when a user requests an API payment.

State the intended Zerion operation and every missing field. Current Scout cannot submit it. A future execution integration must bind intent, chain, token identity, source wallet, destination, maximum spend, minimum received, quote expiry and approval. After submission, retain an identifier and verify the resulting state. Timeouts require reconciliation before retry; silence is not failure proof.


## Unsigned transaction preparation

For a concrete EVM swap, transfer or bridge, use `prepare_zerion_transaction` only when the operator has enabled it. It needs an exact source address, contract addresses (or `native`), a positive decimal amount string and a stable request ID. Bridges also need the destination address and chain. Token symbols do not establish identity. Slippage uses basis points, capped at 500.

The result is unsigned and expires after 120 seconds. `get_zerion_preparation` reads local state. Reusing an ID with a different intent is rejected; repeated or expired requests do not trigger another provider call. Solana preparation, staking, arbitrary payments and signing are unavailable. The returned transaction metadata does not verify swap/bridge calldata semantics. The operator must inspect the unsigned envelope and use a separately authorized Zerion workflow to sign.
