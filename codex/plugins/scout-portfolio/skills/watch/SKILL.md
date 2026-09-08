---
name: watch
description: Builds one on-demand Scout portfolio report from a shared wallet observation
---

# Watch

## Scope

Run one portfolio review per invocation and write a static HTML report. The report covers the observed snapshot, PnL, heuristic asset context, current DCA windows, and saved local alerts.

Scout observes the wallet once. It derives every report panel from that snapshot in memory. This lets API-key and x402 sources use the same report path without multiplying portfolio reads by panel count.

The report is self-contained. It has inline styles, makes no browser fetches, and needs no server after generation. The command overwrites `$SCOUT_REPORT_PATH`, which defaults to `./scout-report.html`.

## Safety rules

- Never sign, submit, execute, route, or claim settlement of a transaction.
- Every indicator carries: `Heuristic indicators, not backtested; treat as descriptive, not predictive.`
- Every DCA-window and alert result carries: `This is analysis, not financial advice.`
- State when price data is stale.
- Alert checks run only during this invocation. Scout creates no daemon, cron job, or push channel.
- In x402 mode, report the remaining process budget shown by the host.

## Run it

```bash
uv run python -m scout_portfolio_manager.reporting_html
```

Source selection matches the MCP server. A complete API-key or x402 configuration selects Zerion. `ZPM_FIXTURE_PATH` selects another fixture. The packaged fixture is the final default.

Set `SCOUT_REPORT_PATH` to change the output file. A scheduler may invoke the same command later; each run remains one isolated pass.

## Output contract

Name the portfolio source and observation time. Mark the synthetic price-history source beside its indicators. Include the x402 budget badge when present.

See `reference.md` for the data contract and `examples.md` for sample runs.
