# Reference: the watch chain and report contract

## Tool chain, in call order

| Step | Tool | Boundary | Called |
|---|---|---|---|
| 1 | `get_portfolio_snapshot` | observe | once |
| 2 | `get_pnl` | calculate | once |
| 3 | `analyze_asset` | calculate | once per held asset |
| 4 | `dca_windows` | propose | once per held asset |
| 5 | `check_alerts` | calculate | once |

No tool in this chain writes, signs, submits, or schedules anything. `set_alert` is not
part of the chain itself; call it separately (CLI, MCP tool call, or `preview_dca`'s own
Python fallback pattern) before a `watch` run to have `check_alerts` evaluate it.

The chain repeats snapshot reads through PnL, analysis, windows, and alerts.
`build_report` refuses an x402-backed host until Scout has a cumulative spend
budget. This prevents an on-demand report or loop tick from multiplying paid calls.

## `render_report`'s inputs

```python
def render_report(
    *,
    snapshot: dict,   # host.get_portfolio_snapshot()["snapshot"]
    pnl: dict,        # host.get_pnl() full response
    analyses: dict,   # {asset: host.analyze_asset(asset)}
    windows: dict,    # {asset: host.dca_windows(asset)}
    alerts: dict,     # host.check_alerts() full response
) -> str: ...
```

Pure rendering: no I/O, no network call of its own, regardless of how the host was
constructed upstream. `build_report(host)` in the same module runs the chain and calls
`render_report` for you.

## Output file

- Default path: `./scout-report.html`, overridable via `SCOUT_REPORT_PATH`.
- Overwritten on every run; no history is kept by this skill.
- Self-contained: inline CSS, no external references, no `<script>` fetch calls.
- Gitignored (`scout-report.html` in `.gitignore`): this is a generated deliverable for
  whoever runs `watch`, not a repo artifact.

## Alert storage

Alert rules persist in `.scout/alerts.json` (gitignored), read fresh on every
`check_alerts` call. A `/loop` tick is a new process each time; without this file, every
rule would be forgotten between ticks.
