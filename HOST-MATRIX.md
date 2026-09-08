# Host matrix

What each install route actually gets, and what the repo can prove about it. Evidence levels: VERIFIED-IN-CI (a test or gate in `.github/workflows/ci.yml` fails if the claim breaks), TESTS (covered by the offline suite, not a separate CI gate), PACKAGE (file inspection), NOT PROVEN (no evidence in this repo).

| Capability | Claude Code plugin | Codex mirror | Generic MCP host (stdio) | Evidence level |
|---|---|---|---|---|
| Skill files included | Yes, `skills/` at plugin root | Yes, generated into `codex/plugins/` | No, skills do not travel over stdio | PACKAGE; `scripts/build_host_layouts.py` generates the mirror |
| MCP server registers exactly the 8 named tools | Yes, via `.mcp.json` | Yes, same stdio config | Yes, `.mcp.json` merges into any MCP client | VERIFIED-IN-CI; `tests/test_execution_boundary.py` pins the live tool set |
| Fixture-backed offline mode is the default | Yes | Yes | Yes | VERIFIED-IN-CI; the whole suite runs offline against `fixtures/portfolio.json` |
| Optional read-only Zerion observation | Yes, when both env vars are set | Yes, same adapter | Yes, same adapter | TESTS; `tests/test_zerion_api.py` covers the adapter, CI makes no live calls |
| Alerts are local on-demand files (`.scout/alerts.json`) | Yes | Yes | Yes | VERIFIED-IN-CI; `tests/test_alerts.py`, `tests/test_host_alerts.py` |
| Execution, signing, or wallet connect | Not included | Not included | Not included | VERIFIED-IN-CI; AST import-graph scan plus tool-set pin in `tests/test_execution_boundary.py` |
| Fresh-host automatic activation | Not proven | Not proven | Not proven | No evidence in this repo; hosts may require an explicit install or restart step |
| Cursor.app end-to-end smoke test | n/a | n/a | Not proven | CLAIMS.md: "Cursor.app smoke-test may still be pending" |

The 8 tools: `get_portfolio_snapshot`, `get_pnl`, `parse_dca_request`, `preview_dca`, `analyze_asset`, `dca_windows`, `set_alert`, `check_alerts`.

Claude Code is the primary host; Codex and plain stdio are fallbacks (see `RELEASE-MANIFEST.json`). Boundaries and claims: [`CLAIMS.md`](CLAIMS.md), [`SECURITY.md`](SECURITY.md).
