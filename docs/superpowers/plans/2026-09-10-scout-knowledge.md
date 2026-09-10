# Scout knowledge implementation plan

> For agentic workers: use Superpowers subagent-driven-development for bounded independent tasks. User waived interim human reviews and delegated design decisions.

Goal: implement the source-linked knowledge and portfolio analysis proposal defined in the companion spec.
Architecture: pure advisory calculations and local knowledge feed the existing Scout host; the public MCP registry exposes bounded tools. Execution remains unavailable for portfolio actions.
Tech stack: Python 3.11, Pydantic, existing FastMCP and pytest; no new runtime dependency.
Spec: docs/superpowers/specs/2026-09-10-scout-knowledge-design.md

## Global constraints

- Zerion is the only named execution provider in Scout action plans; no new signer or submitter.
- No real paid calls, secret reads, installed harness changes, pushes or publication.
- All calculations label input provenance and limits; no invented rates or complete risk claims.
- Keep private vault context outside public package.

## Task 1: Pure advisory calculations

Files: create src/scout_portfolio_manager/advisory.py and tests/test_advisory.py.
Consumes PortfolioSnapshot. Produces portfolio_risk(snapshot, shock_pct=-30.0), assess_yield(principal_usd, base_apr_pct, reward_apr_pct=0.0, borrow_apr_pct=0.0, fees_usd=0.0, days=365), plan_zerion_action(action, asset=None, amount=None, chain=None, destination=None).

- [x] Write known-answer tests first: holdings 60/40 -> HHI .52, effective count 1/.52, 30% fall -> 70; yield 1000 at 5% for 365d minus 10 fees -> 40; action swap -> no execution, provider Zerion.
- [x] Run failing tests; implement pure functions, finite validation and explicit gaps.
- [x] Cover duplicate labels, zero balances, invalid dates/numbers, unsupported actions and absent fields; run tests and Ruff.

## Task 2: Source-linked local knowledge

Files: knowledge.py, data/defi_knowledge.json, tests/test_knowledge.py; skills/defi-research and portfolio-intelligence routing.
Produces search_knowledge(query, ecosystem=None, limit=5). Read source corpus only from package resources.

- [x] Test PDA, impermanent loss, bridge risk, LST, reward APR, unknown term and invalid limit.
- [x] Implement bounded lexical/alias lookup, stable source IDs and output disclaimers.
- [x] Write original concise cards with maintained reference URLs; never load external skill instructions as executable context.

## Task 3: Host and plugin integration

Files: host.py, mcp_server.py, registry tests, package/host documentation, manifests and source notices.
Consumes Task 1 and Task 2 functions. Public tools: get_portfolio_risk, assess_defi_yield, search_defi_knowledge, plan_zerion_action.

- [x] Register functions in direct host dispatch and MCP, add input schemas and integration assertions.
- [x] Update skills, agent instructions, current claims and all maintained manifests; retain historical release status.
- [x] Prepare Grok Build catalog submission candidate only after verifying current schema and ownership requirements.

## Task 4: Verify and show the result

- [x] Run existing/full/new tests, Ruff, mypy, security scan and manifest checks.
- [x] Run real stdio MCP calls, wheel install from another cwd and release archive checks.
- [x] Run baseline rollback smoke and record exact output.
- [x] Produce source/brainstorm/plan/build report, patch, package, PR text and visual review in outputs/.

## Preflight

| Pair | Shared boundary | Resolution |
|---|---|---|
| 1 / 3 | advisory function signatures | exact names above; worker owns module and tests only |
| 2 / 3 | knowledge search | exact signature above; parent owns both |
| 3 / 4 | registry and manifests | regenerate after integration, then verify packaged files |

Ruling: prepare local PR material; user reviews before publication. Ruling: proposal-only action interface follows observed missing execution capability. Ruling: use curated original content with source links to avoid importing foreign tool authority and stale guidance.
