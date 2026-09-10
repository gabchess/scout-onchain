# Independent DeFi review

A separate AI reviewer wrote and froze twelve hypothetical DeFi cases before seeing Scout's responses. The baseline passed 11 case gates. It failed the suite gate because one critical disclosure was incomplete. [Read the full baseline review](REVIEW.md) for each criterion and its evidence.

The baseline source was `7d2e5dd8ad5cd5045c57f2b7bdf1280b6fab3ff9`. Evaluation used Codex CLI with injected Scout skills and fixture MCP access. This measures answers in that setup. Native plugin activation and live financial behavior were outside the test.

Corrections clarify token-holder revocation limits, liquidation trigger interpretation, withdrawal mechanisms and variable funding. The published cases are now regression tests. Follow-up results retain the first failure and distinguish new holdout cases from repeated ones.

The rubric, criteria and reference answers are in [suite.json](suite.json). The answering host received only the prompts. [grades.json](grades.json) records criterion scores and response hashes; [the author report](author-report.md) sets the weighting and gates.

To run another evaluation, follow [the protocol](../../docs/INDEPENDENT-EVALUATION.md). Keep a fresh suite private until its first run. One separate AI review provides bounded evidence and does not establish human expert approval or production performance.
