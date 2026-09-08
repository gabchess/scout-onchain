# Zerion portfolio-manager agent demo

A self-contained, fixture-backed demo UI for the read-only portfolio
intelligence in this repository. One page shows the whole agent loop:

1. **Portfolio snapshot** (boundary: *observe*): holdings and the transaction
   ledger from the synthetic fixture at `fixtures/portfolio.json`.
2. **Explainable USD PnL** (boundary: *calculate*): realized, unrealized, and
   total, with the formula, basis provenance, and confidence shown, not just
   a number.
3. **DCA agent** (boundary: *propose/approve*): type a natural-language DCA
   request. Missing details produce a clarification question, never a guess.
   A complete request produces a preview with `approval_state=required` and
   `execution_available=false`.

The demo is a thin window onto `scout_portfolio_manager.host.ReadOnlyHost`.
It adds no portfolio logic and no execution capability of any kind.

Execution boundary: not implemented in this host. A DCA request ends at a
complete, approval-required preview. Wallet connection and execution are
outside the current capability.

## Safety boundary

`observe ≠ calculate ≠ propose ≠ approve ≠ execute ≠ verify`

- No wallet connect, no signing, no transaction submission, no fund movement,
  no investment advice.
- The demo server exposes eight fixture-backed endpoints. It has no execute,
  sign, or submit route.
- Runs entirely offline on the synthetic fixture. It makes no live Zerion
  API call. `ZERION_API_KEY` is **not** required and is never read by the
  demo. Fixture values are examples, not live market data.

## Run it

From the repository root, with [`uv`](https://docs.astral.sh/uv/) installed:

```bash
uv run --project . demo/zerion-portfolio-agent/server.py
```

`uv run` resolves the project's one dependency, `pydantic>=2.5`, from
`pyproject.toml`/`uv.lock` and runs the server in that environment. No
manual venv or install step is needed.

Then open http://127.0.0.1:8787.

If port 8787 is taken, pick another:
`DEMO_PORT=8899 uv run --project . demo/zerion-portfolio-agent/server.py`.

### Without uv

Python 3.11+ is required. A bare `python3` on some machines resolves to an
older interpreter that lacks PEP 660 support, which `pip install -e` needs:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python demo/zerion-portfolio-agent/server.py
```

(Any environment where the package's one dependency, `pydantic>=2.5`, is
importable works. The server adds `src/` to `sys.path`, so a plain
`pip install 'pydantic>=2.5'` followed by
`python3.11 demo/zerion-portfolio-agent/server.py` also runs.)

## Things to try

- Click **incomplete, then clarification** (`DCA another $300 of ETH`): the intent
  grid shows which fields parsed and which are missing, and the agent asks a
  clarification question instead of inferring a chain, schedule, or wallet.
- Click **complete, then preview**
  (`DCA $300 ETH on ethereum weekly from wallet:0xabc123 to wallet:0xdef456`):
  a full preview renders with `approval_state: required`,
  `execution_available: false`, and every assumed quote value labeled as a
  fixture placeholder.

## Files

| File | Purpose |
|---|---|
| `server.py` | Stdlib HTTP server wrapping `ReadOnlyHost`; serves the API + static UI |
| `static/index.html` | Product chrome: pipeline strip, snapshot, PnL, DCA agent panels |
| `static/app.js` | Fetches host responses and renders them; no portfolio logic |
| `static/styles.css` | Dashboard styling |

## API surface (all read-only)

| Endpoint | Host method |
|---|---|
| `GET /api/snapshot` | `get_portfolio_snapshot()` |
| `GET /api/pnl?asset=ETH` | `get_pnl(asset)` |
| `GET /api/analyze?asset=ETH` | `analyze_asset(asset)` |
| `GET /api/dca-windows?asset=ETH` | `dca_windows(asset)` |
| `GET /api/alerts` | `check_alerts()` |
| `GET /api/report` | `reporting_html.build_report(host)` |
| `POST /api/dca/parse` `{"text": …}` | `parse_dca_request(text)` |
| `POST /api/dca/preview` `{"text": …}` | `preview_dca(text)` |

Anything else returns 404, including any execute, sign, or submit path.
