# Knowledge and advisory proposal

Scout 0.5.0 release candidate. The advisory layer adds four tools. Two additional optional unsigned preparation tools are described in [the preparation contract](../ZERION-PREPARATION.md). The package adds no signer for the observed wallet or trade executor.

| Tool | Input | Result | Network |
|---|---|---|---|
| `get_portfolio_risk` | Optional uniform `shock_pct`, -100 to 100 | Gross USD allocation, weights, HHI, effective position count, source age and scenario | One configured portfolio read; x402 mode can pay for it |
| `assess_defi_yield` | Principal USD, base/reward/borrow APR percentages, fees USD, days | Simple, non-compounding yield components | None |
| `search_defi_knowledge` | Query, optional ecosystem, 1..8 results | Curated source-linked concepts or attributed community terms | None |
| `plan_zerion_action` | Action and known asset/amount/chain/destination | Zerion-only plan with missing fields and no execution | None |

The corpus includes 48 original Scout learning cards and 1,059 imported SolanaBR glossary entries. These counts measure coverage, not expert correctness. Original cards cover portfolio concentration and look-through, DeFi yield, lending, LPs, bridges, market structure, Ethereum and Solana. The community definitions have not each been independently fact-checked. They carry `community_reference_unverified`, source revision and file. They can contain dated numeric limits and software behavior. Check those claims against current primary documentation.

All lookups are local package reads. Query scoring uses title, aliases and keywords with curated matches ranked ahead of equivalent community matches. Lookup never fetches or runs an external skill. Unknown queries return no_match. The official Solana terminology is linked in the source lock and has not been copied; ETH Skills is reference-only because its license evidence is incomplete.

## Examples

```python
from scout_portfolio_manager.host import default_host

host = default_host()
print(host.get_portfolio_risk(shock_pct=-30))
print(host.assess_defi_yield(1000, 5, fees_usd=10))
print(host.search_defi_knowledge("PDA", ecosystem="solana"))
print(host.plan_zerion_action("swap", asset="USDC", amount=100, chain="base"))
```

The first fixture is $2,250 of ETH; a uniform -30% scenario is $1,575. The yield example produces $40 net under the stated assumptions. Neither example reports a live market result.

Weights are fractions, and HHI is the sum of squared fractional weights. Effective count is 1/HHI for a positive-value portfolio. A user portfolio may include debt, vault claims, correlated wrappers and offchain assets absent from this snapshot. The tool cannot compute complete net worth, liquidation risk or correlation-adjusted diversification from missing information.

Yield rates all apply to the same supplied principal. Different borrowing notionals require a separate calculation. Advertised APY must not be passed as APR without a conversion. The tool excludes price changes, fees beyond the supplied amount, varying rates, taxes, liquidation and compounding.

The 15-minute freshness indicator labels the observed portfolio timestamp. It is a local convention, not a provider SLA. Future or timezone-free timestamps remain explicit. A recent timestamp does not prove the source includes all positions.

## Reproduce in Docker

```bash
docker build -f Dockerfile.sandbox -t scout-review .
docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges scout-review
```

The image build downloads pinned dependencies from `uv.lock`. The test container has no host mounts, credentials or network. Container tests validate offline behavior; they cannot establish live Zerion payments or host UI activation.

## Maintain the glossary

```bash
python3 scripts/import_solana_glossary.py --help
```

The importer takes an explicit local checkout; it does not download or refresh itself. Retain the exact SHA and full MIT notice when updating. See [source lock](SOURCE-LOCK.json) and [third-party notices](../../THIRD-PARTY-NOTICES.md).

## Evaluation boundary

The tests check retrieval and numerical answers. They do not prove that an arbitrary model follows the skills or gives good advice. Use the held-out scenarios in `evals/knowledge-cases.json` to test a real host after installation. Preserve its raw responses and source/tool traces. Score factual support, calibrated uncertainty, relevance and action restraint separately; do not report a combined quality score from static keyword tests.

The dated [host evaluation report](../../evals/HOST-EVALUATION.md) records two completed 12-case runs and their limitations.
