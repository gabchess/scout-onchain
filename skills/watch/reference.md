# Watch report contract

## Calculation path

`build_report(host)` calls `host.build_report_data()`. The host performs one wallet snapshot, then derives these panels in memory:

| Panel | Boundary | Input |
|:--|:--|:--|
| Portfolio | observe | Shared snapshot |
| PnL | calculate | Holdings and mapped transactions |
| Asset analysis | calculate | Shared snapshot plus bundled price history |
| DCA windows | propose | Asset analysis |
| Alerts | calculate | Saved rules plus shared analysis and PnL |

No report step writes a transaction or schedules work. `set_alert` is outside the report chain and writes only `.scout/alerts.json`.

In x402 mode, each payment payload reserves the full configured per-payment cap. A recovery payload consumes another reservation. The rendered header shows the remaining process budget.

## `render_report` inputs

```python
def render_report(
    *,
    snapshot: dict,
    pnl: dict,
    analyses: dict,
    windows: dict,
    alerts: dict,
    x402_spend_budget: dict | None = None,
) -> str: ...
```

Rendering performs no I/O or network call.

## Output file

- Default path: `./scout-report.html`, overridable with `SCOUT_REPORT_PATH`.
- Each run overwrites the previous file.
- The document contains inline CSS and no external request.
- The path is gitignored.

## Alert storage

Alert rules persist in `.scout/alerts.json` and are read during each check. A new process uses the same file when it runs from the same working directory.
