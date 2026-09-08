# Product brief

## Purpose

This repository explores a portable portfolio-intelligence surface for agent workflows. It reads portfolio data, explains PnL, clarifies DCA intent, and stops at preview.

## Available evidence

The repository includes a synthetic fixture, an eight-tool host, a Zerion positions and transactions adapter, and stdio MCP. Tests cover documented behavior offline. API-backed behavior depends on the configured access, endpoint contract, and network.

## What this project does not claim

This repository does not make claims about Zerion's architecture, SLOs, customer demand, product endorsement, or endpoint guarantees. It is not a production integration, trading system, wallet, signing service, or investment-advice product.

## Questions for an integration owner

- Which portfolio fields, freshness indicators, and cost-basis gaps belong in an agent contract?
- What authorization, rate-limit, quote-expiry, and error semantics should an approved integration expose?
