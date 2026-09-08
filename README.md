# Scout

<p align="center">
  <img src="docs/scout-mascot-corgi.png" width="180" height="180" alt="Scout, a corgi mascot for the portfolio intelligence plugin" />
</p>

<p align="center"><strong>Portfolio intelligence for AI agents.</strong></p>

<p align="center">
  <a href="CLAIMS.md"><img alt="version 0.4.0" src="https://img.shields.io/badge/version-0.4.0-0B57D0" /></a>
  <a href="LICENSE.md"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-2ea44f" /></a>
  <a href="SECURITY.md"><img alt="MCP has no trading tools" src="https://img.shields.io/badge/MCP-no--trade-6e7781" /></a>
</p>

Ask your agent what a wallet owns and how the portfolio performed. Scout starts with sample data. Zerion reads require an API key or x402.

The observed wallet supplies an address only. A separate x402 wallet signs USDC payments for data access. Scout has no trade execution tool.

## Ask Scout

| Ask | Result |
|:--|:--|
| Show me what I own | Holdings and mapped transactions |
| What is my PnL? | Cost basis with realized and unrealized PnL |
| Preview a weekly ETH DCA | Parsed intent with `approval_state=required` |
| Alert me below a price | A rule in local `.scout/alerts.json` |

DCA requests end at preview. Indicators use synthetic prices with low confidence.

## Start with sample data

```bash
uv sync --extra test --extra mcp
uv run pytest -q
uv run --extra mcp zpm-mcp
```

Then ask:

> Show me what I own and what it did.

The fixture needs no key or network. See [`START-HERE.md`](START-HERE.md) for each host.

## See the agent loop

```bash
uv run --project . demo/zerion-portfolio-agent/server.py
```

Open `http://127.0.0.1:8787`.

<p align="center">
  <img src="docs/zerion-portfolio-demo-screenshot.png" width="720" alt="Scout demo with a portfolio snapshot, PnL, and DCA preview" />
</p>

## Use Zerion

API-key mode needs `ZERION_API_KEY` with `ZERION_WALLET_ADDRESS`.

x402 mode needs `ZERION_X402_PRIVATE_KEY`, `ZERION_WALLET_ADDRESS`, and the `x402` dependency extra. Use a dedicated payment wallet with a small USDC balance on Base.

The default x402 cap is `$0.05` per payment. Scout has no cumulative spend cap. A snapshot can make 21 top-level requests at the default page limit, and the SDK can attempt paid recovery inside one request.

Tests cover SDK construction and failures without sending funds. No paid live test is recorded. Read [`docs/X402.md`](docs/X402.md) before enabling payments.

## Evidence

See [`CLAIMS.md`](CLAIMS.md) for status, [`HOST-MATRIX.md`](HOST-MATRIX.md) for host checks, and [`SECURITY.md`](SECURITY.md) for signing boundaries. [MIT licensed](LICENSE.md).
