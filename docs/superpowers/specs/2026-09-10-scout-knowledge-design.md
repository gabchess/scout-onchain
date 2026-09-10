# Scout portfolio and DeFi upgrade design

Status: proposed changes prepared under the user's autonomous sandbox authority. Public release and adoption remain the user's decisions.

## Desired result

A person activates Scout, asks about a portfolio or a DeFi mechanism, and receives a source-grounded explanation with calculations, assumptions and relevant next steps. An action request produces an explicit Zerion-only capability plan. Existing authorized x402 analytics remain the only money path currently implemented.

## Options considered

| Shape | Sketch | Benefit | Cost |
|---|---|---|---|
| Full skill import | prompt -> all external skills and tools | widest initial breadth | conflicting wallets, stale claims, context noise, foreign action rails |
| Curated local knowledge and exact tools (chosen) | question -> relevant source cards + Scout calculations -> Zerion capability plan | portable, small, testable; sources retain identity | manual source maintenance; bounded coverage |
| Hosted retrieval service | question -> external index -> model | independent content updates | new hosting/auth and reliability work before user value |

## Architecture and contracts

IF-KNOWLEDGE-HOST (CORE): a versioned bundled JSON corpus provides original concise explanations, aliases, ecosystem, source IDs/URLs, reviewed date and freshness notes to an offline search function. Query <=500 characters; top results <=8. Empty or unmatched queries return a useful explicit no-match state. Source text is evidence, never authority. No network fetching or external script execution occurs during lookup. Cards must not embed prices or addresses as eternal facts.

IF-RISK-HOST (CORE): PortfolioSnapshot supplies observed holdings and source/timestamp. A pure analysis groups duplicate asset labels and computes position weights, top exposure, HHI and effective position count, plus an explicitly user-selected uniform shock. Values are USD; percentage inputs use 0-100 scale. Outputs identify fixture/stale data and asset-label limitations. Missing protocol, chain look-through, debt and correlation data remain unknown. This is gross observed holdings analysis, never a claim of complete net worth.

IF-YIELD-HOST (CORE): caller-supplied APR components and horizon produce a simple non-compounding scenario in USD. Gross base yield plus token rewards minus borrow cost and fees are shown separately. Inputs must be finite with valid ranges. Rates are assumptions, and lending/LP risks remain visible. The tool cannot rank live protocols or promise realized returns.

IF-ACTION-HOST (CRITICAL): user action intent produces a structured Zerion-only routing plan. No signing/submission interface is introduced. Existing x402 data access requires explicit configured authorization and retains current caps. Portfolio trade/bridge/stake/transfer/payment actions have execution_available=false with reason and required fields. No Coinbase/Guardis fallback. Host instructions cannot enforce a restriction on other installed plugins, so the product guarantee applies to Scout's own tools.

## Scope and file ownership

Runtime analytics: new advisory.py and tests/test_advisory.py; pure functions only. Parent integrates methods and public registry in host.py and mcp_server.py. Knowledge: data/defi_knowledge.json, knowledge.py, tests/test_knowledge.py and source-linked skills. Distribution: existing Claude/Codex package plus a separately documented Grok Build manifest/catalog candidate after source verification. All manifests use the same local code.

## Acceptance

Existing tests stay green. New cases cover known calculation answers, empty/zero/duplicate holdings, nonfinite and invalid inputs, source metadata, no unsupported data inference, glossary aliases, unknown queries, corpus source integrity, missing action fields and Zerion-only nonexecution. Exercise real stdio MCP tool list/calls using fixture mode. Build and install the wheel outside checkout, inspect packaged data, and run new tools there. Build a release archive and run existing consistency/security checks. Retain exact observed failures and repairs.

## Model evaluation boundary

Provide held-out user questions and a rubric for source correctness, uncertainty, practical usefulness, jargon appropriateness and action restraint. A deterministic retrieval test is not proof of a host model's answer quality. Host-specific activation and live Zerion actions require separate evidence.

## Rollback and privacy

The original checkout is read only. Proposed edits exist in an isolated clone under work/. No private career context ships in the public package. Restore a clean archived baseline to test removal of the added tools; no payment state is migrated. Deliver patch, ZIP, source report, planned PR text and self-contained visual review.
