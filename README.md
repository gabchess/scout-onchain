# Scout

<p align="center">
  <img src="docs/scout-mascot-corgi.png" width="180" height="180" alt="Scout, a corgi mascot for the onchain portfolio manager" />
</p>

<p align="center"><strong>An onchain portfolio manager for AI agents.</strong></p>

<p align="center">
  <a href="CLAIMS.md"><img alt="version 0.4.0" src="https://img.shields.io/badge/version-0.4.0-0B57D0" /></a>
  <a href="LICENSE.md"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-2ea44f" /></a>
  <a href="SECURITY.md"><img alt="DCA proposal only" src="https://img.shields.io/badge/DCA-proposal-6e7781" /></a>
</p>

Scout gives an LLM agent a focused set of portfolio tools. The agent can inspect a wallet, explain PnL, compare a DCA window, draft a DCA proposal, or check local alerts. It chooses the smallest useful path from the user's request.

The host is customizable. It works with bundled sample data, a Zerion API key, or Zerion's x402 payment flow. The observed wallet is always an address-only input.

## What to ask

| User request | Scout route |
|:--|:--|
| Show me what I own | Portfolio snapshot and mapped transactions |
| What is my PnL? | Cost basis with realized and unrealized PnL |
| Is this a useful DCA window? | Low-confidence heuristic analysis |
| Draft a weekly ETH DCA | Clarified intent and an approval-required proposal |
| Check my alerts | One local, on-demand evaluation |

Market indicators and DCA windows use bundled synthetic price history in 0.4.0. Scout labels that source and keeps confidence low.

Every DCA flow stops at a proposal. `preview_dca` returns `approval_state=required` and `execution_available=false`. Scout does not connect the observed wallet, sign a trade, or submit a transaction.

## Try it

Python 3.11 and [`uv`](https://docs.astral.sh/uv/) are required for this path.

```bash
uv sync --extra test --extra mcp
uv run pytest -q
uv run --extra mcp zpm-mcp
```

The default fixture needs no key or network access. Add Scout to Claude Code, Codex, Cursor, or another stdio MCP client with [`START-HERE.md`](START-HERE.md).

To see the local agent loop:

```bash
uv run --project . demo/zerion-portfolio-agent/server.py
```

Open `http://127.0.0.1:8787`.

<p align="center">
  <img src="docs/zerion-portfolio-demo-screenshot.png" width="720" alt="Scout demo with a portfolio snapshot, PnL, and DCA proposal" />
</p>

## Use Zerion

API-key access needs `ZERION_API_KEY` and `ZERION_WALLET_ADDRESS`. Scout reads Zerion positions and mapped transactions. A host may pass external quote fields into `preview_dca`; Scout 0.4.0 does not fetch a swap quote itself.

x402 access needs `ZERION_X402_PRIVATE_KEY`, `ZERION_WALLET_ADDRESS`, and the `x402` dependency extra. This route pays for analytics reads from a separate Base wallet. It does not authorize trading.

Scout reserves the full per-payment cap before each x402 signature. The defaults are `$0.05` per payment and `$1.05` for the process lifetime. SDK recovery payments count against the same budget. A watch report shares one wallet snapshot across its panels.

The x402 suite runs without sending funds. This repository has no verified paid live request. Read [`docs/X402.md`](docs/X402.md) before adding a payment key.

## Evidence

[`CLAIMS.md`](CLAIMS.md) records what is tested. [`SECURITY.md`](SECURITY.md) explains each authority boundary. The package is [MIT licensed](LICENSE.md).
