# Scout

> **Scout 0.7.0:** Install Scout in Claude Code, Codex or Cursor with no clone, and try it with `/scout-portfolio:try`. The browser demo is gone. x402 now needs `SCOUT_ENABLE_X402=1`. See [release downloads](https://github.com/gabchess/scout-onchain/releases/tag/v0.7.0), [what changed](CHANGELOG.md) and [claim status](CLAIMS.md).

<p align="center">
  <img src="docs/scout-mascot-corgi.png" width="180" height="180" alt="Scout, a corgi mascot for the onchain portfolio manager" />
</p>

<p align="center"><strong>An onchain portfolio manager for AI agents.</strong></p>

<p align="center">
  <a href="CLAIMS.md"><img alt="version 0.7.0" src="https://img.shields.io/badge/version-0.7.0-0B57D0" /></a>
  <a href="LICENSE.md"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-2ea44f" /></a>
  <a href="SECURITY.md"><img alt="DCA proposal only" src="https://img.shields.io/badge/DCA-proposal-6e7781" /></a>
</p>

Scout gives an LLM agent a focused set of portfolio tools. The agent can inspect a wallet, explain PnL, compare a DCA window, draft a DCA proposal, or check local alerts. It chooses the smallest useful path from the user's request.

The host is customizable. It works with bundled sample data, a Zerion API key, or Zerion's x402 payment flow. Zerion reads include Arc, Circle's USDC-gas chain. The observed wallet is always an address-only input.

## What to ask

| User request | Scout route |
|:--|:--|
| Show me what I own | Portfolio snapshot and mapped transactions |
| What is my PnL? | Cost basis with realized and unrealized PnL |
| Is this a useful DCA window? | Low-confidence heuristic analysis |
| Draft a weekly ETH DCA | Clarified intent and an approval-required proposal |
| Check my alerts | One local, on-demand evaluation |

Market indicators and DCA windows use bundled synthetic price history in 0.7.0. Scout labels that source and keeps confidence low.

Every DCA flow stops at a proposal. `preview_dca` returns `approval_state=required` and `execution_available=false`. Scout does not connect the observed wallet, sign a trade, or submit a transaction.

## Install in your agent

Scout runs as a local stdio MCP server. You need [`uv`](https://docs.astral.sh/uv/) on your PATH; it fetches Python 3.11+ and Scout's dependencies on first start. No clone and no absolute paths.

**Claude Code**

```bash
claude plugin marketplace add gabchess/scout-onchain
claude plugin install scout-portfolio@scout-portfolio-manager
```

Restart Claude Code. The marketplace tracks the default branch unless you add a ref.

**Codex**

```bash
codex plugin marketplace add gabchess/scout-onchain --ref v0.7.0
codex plugin add scout-portfolio --marketplace scout-portfolio-manager
codex mcp add scout-portfolio -- uvx --from git+https://github.com/gabchess/scout-onchain@v0.7.0 scout-portfolio-manager
```

The first two commands install the skills. The third attaches the tools. Restart Codex.

**Cursor or any stdio MCP client**

```json
{
  "mcpServers": {
    "scout-portfolio": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/gabchess/scout-onchain@v0.7.0", "scout-portfolio-manager"]
    }
  }
}
```

**Without uv**

```bash
pipx run --spec git+https://github.com/gabchess/scout-onchain@v0.7.0 scout-portfolio-manager
```

`scout-portfolio-manager` and the older `zpm-mcp` start the same server. Per-host details and evidence are in [`START-HERE.md`](START-HERE.md) and [`HOST-MATRIX.md`](HOST-MATRIX.md).

## Try it in your agent

In Claude Code, run `/scout-portfolio:try`. On other hosts, ask:

> Show me what I own and what it did.

The tour runs on bundled synthetic data. It needs no key and reads no wallet. It shows risk, PnL and a weekly DCA proposal, and names the fixture as the source in every block.

## Use your own data

Scout reads your wallet when its server starts with `ZERION_API_KEY` and `ZERION_WALLET_ADDRESS`. Put them in host config, never in chat. If a key lands in a chat transcript, rotate it.

- Claude Code: export both variables in the shell that launches Claude Code, then restart. The plugin forwards only these two.
- Codex: add `env_vars = ["ZERION_API_KEY", "ZERION_WALLET_ADDRESS"]` under `[mcp_servers.scout-portfolio]` in `~/.codex/config.toml`, then restart.
- Cursor and other clients: add an `env` block with both variables to the Scout entry, and keep that file out of version control.

## Use Zerion

API-key access needs `ZERION_API_KEY` and `ZERION_WALLET_ADDRESS`. Scout reads Zerion positions and mapped transactions. A host may pass external quote fields into `preview_dca`; the standard analytics flow does not fetch a swap quote itself.

x402 access needs `SCOUT_ENABLE_X402=1`, `ZERION_X402_PRIVATE_KEY`, `ZERION_WALLET_ADDRESS`, `ZERION_X402_PAY_TO`, and the `x402` dependency extra, set on your own MCP server entry. The Claude Code plugin sets `SCOUT_ENABLE_X402` to empty, which overrides an exported shell value; do not export it in your shell, because other entries inherit it. This route pays for analytics reads from a separate Base wallet. It does not authorize trading.

Scout reserves the full per-payment cap before each x402 signature. The defaults are `$0.05` per payment and `$1.05` for the process lifetime. SDK recovery payments count against the same budget. A watch report shares one wallet snapshot across its panels.

Before signing, Scout accepts only exact Base mainnet USDC requirements with an explicit recipient, a timeout no longer than 600 seconds, and an amount within the configured cap. `ZERION_X402_PAY_TO` is required and pins the one address it may pay. It also refuses a paid retry that lacks the `PAYMENT-SIGNATURE` header.

The x402 suite runs without sending funds. This repository has no verified paid live request. Read [`docs/X402.md`](docs/X402.md) before adding a payment key.

## Contributing

```bash
git clone https://github.com/gabchess/scout-onchain
cd scout-onchain
uv sync --all-extras
uv run pytest -q
```

## Evidence

[`CLAIMS.md`](CLAIMS.md) records what is tested. [`SECURITY.md`](SECURITY.md) explains each authority boundary. The package is [MIT licensed](LICENSE.md).

## DeFi research and optional preparation

Scout adds source-linked Ethereum and Solana knowledge, portfolio exposure analysis and transparent yield arithmetic. Community glossary entries carry provenance and require current primary-source checks for operational decisions. See [knowledge coverage](docs/knowledge/README.md).

An optional Zerion CLI adapter prepares unsigned EVM swap, transfer and bridge proposals. It starts disabled and has no signing or broadcast path. Read [configuration and evidence limits](docs/ZERION-PREPARATION.md) before enabling it.

Grok Build accepts the Claude plugin layout in this repository. Grok Bot distribution has a separate validation path; see [Grok compatibility](docs/GROK.md).
