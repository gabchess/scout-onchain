---
name: watch
description: Runs Scout's full observe-through-alert chain on demand and writes scout-report.html
---

# Watch

## Scope

One on-demand pass per invocation. It has no trade execution, daemon, cron, or push.
Alert rules live in `.scout/alerts.json` across processes.

Chains five portfolio tools in order:

1. `get_portfolio_snapshot` (observe)
2. `get_pnl` (calculate)
3. `analyze_asset`, once per held asset (calculate)
4. `dca_windows`, once per held asset (propose)
5. `check_alerts` (calculate)

Then writes a static, self-contained HTML report to `$SCOUT_REPORT_PATH`
(default `./scout-report.html`), overwriting whatever was there from the
previous run. No fetch calls, no external script or style references: the
report is a plain file with no server dependency.

x402 mode is blocked. One report makes several snapshot calls, and Scout has
no cumulative payment budget. Use fixture or API-key mode for `watch`.

## Safety rules

Same boundary as `skills/portfolio-intelligence/`, restated because this skill runs
unattended:

- Never sign, submit, execute, route, or claim settlement of a transaction.
- Never infer a chain, schedule, source wallet, destination wallet, amount, or asset.
- Every indicator carries the disclosure: `"Heuristic indicators, not backtested; treat as descriptive, not predictive."`
- Every DCA-window and alert result carries the line: `"This is analysis, not financial advice."`
- If price data is stale, say so. Never suppress an indicator or silently decide a
  fire/no-fire alert outcome on stale data.
- `set_alert`/`check_alerts` never run in the background. This skill's own invocation is
  the only trigger; nothing here schedules itself.

## Running it

Direct Python entry point, no MCP server needed:

```bash
uv run python -m scout_portfolio_manager.reporting_html
```

Source selection matches the MCP server: API-key Zerion when its two variables
are set, then `$ZPM_FIXTURE_PATH`, then the packaged fixture. An x402 source
stops with a spend-safety error. Set `SCOUT_REPORT_PATH` to change the output.

Under `/loop`, point the loop at this same command; each tick re-runs the chain once and
overwrites the report.

## Output shape

Report panels: portfolio snapshot (observe), PnL (calculate), technical indicators per
held asset (calculate, including each `dca_windows` label), and alerts (calculate,
empty-state text when no rules are set). State the source (fixture vs. Zerion API) and
whether any indicator is flagged stale.

See `reference.md` for the report's data contract and `examples.md` for sample runs.
