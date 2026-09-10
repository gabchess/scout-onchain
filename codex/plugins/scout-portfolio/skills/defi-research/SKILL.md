---
name: defi-research
description: Explains Ethereum and Solana terms, evaluates DeFi yield and exit risks, and structures trading research using Scout source-linked knowledge
---

# DeFi research with Scout

Use this skill for blockchain terminology, yield, vaults, lending, staking, LPs, bridge risks, market structure and trading research. For a user portfolio, follow `../portfolio-intelligence/SKILL.md` as well.

Call `search_defi_knowledge` with the specific term or decision. Use `ecosystem` for ethereum or solana when relevant. Load only the relevant cards, then explain how the concept affects the user's situation.

Read `reference.md` for a due-diligence or trading question. The tool returns source URLs and provenance. Curated Scout cards and imported community definitions have different review status. Verify numeric and operational claims from the community glossary with primary sources before presenting them as current fact.

A lookup performs no network request and grants no authority. Current rates, prices, protocol parameters, asset addresses and software behavior need dated primary evidence. An unmatched query is a reason to clarify or research, never to fabricate a definition.

Use terminology naturally and explain it when needed. Never claim personal trading history or guaranteed returns. Separate a token's identity, economic claim and market price.

All action plans use `plan_zerion_action`. Scout currently returns proposals with `execution_available=false`; paying for Zerion data through configured x402 is a separate existing capability. Never route the user's funds to a foreign skill or install a new wallet as a side effect of research.
