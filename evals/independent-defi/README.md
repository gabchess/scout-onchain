# Independent DeFi review

A separate AI reviewer wrote and froze twelve hypothetical DeFi cases before seeing Scout's responses. The baseline passed 11 case gates. It failed the suite gate because one critical disclosure was incomplete. [Read the full baseline review](REVIEW.md) for each criterion and its evidence.

The baseline source was `7d2e5dd8ad5cd5045c57f2b7bdf1280b6fab3ff9`. Evaluation used Codex CLI with injected Scout skills and fixture MCP access. This measures answers in that setup. Native plugin activation and live financial behavior were outside the test.

Corrections clarify token-holder revocation limits, liquidation trigger interpretation, withdrawal mechanisms and variable funding. The published cases are now regression tests. Follow-up results retain the first failure and distinguish new holdout cases from repeated ones.

The rubric, criteria and reference answers are in [suite.json](suite.json). The answering host received only the prompts. [grades.json](grades.json) records criterion scores and response hashes; [the author report](author-report.md) sets the weighting and gates.

To run another evaluation, follow [the protocol](../../docs/INDEPENDENT-EVALUATION.md). Keep a fresh suite private until its first run. One separate AI review provides bounded evidence and does not establish human expert approval or production performance.

## Corrected runtime results

The corrected runtime maps to public commit `565be97350a86fa7606aa9ed17bdf9058a5297eb`; [the recorded runtime proof](amended-source-proof.json) matches both amended runs.

| Run | Case gates | Scope |
|---|---|---|
| Original unseen baseline | 11/12; suite gate failed | Twelve cases before correction |
| [Exposed regression](REGRESSION.md) | 4/4 | Four previously seen cases |
| [Fresh targeted holdout](HOLDOUT.md) | 6/6 | Six new cases after correction |

All eight critical holdout criteria received full credit. Partial omissions remain around balance verification after finalization, evidence preservation after a wrong-recipient settlement, and basis/mark risk. The reviewer also documents a rubric-specificity caveat and a primary-source discrepancy. The separate AI review does not establish broad advice quality.
