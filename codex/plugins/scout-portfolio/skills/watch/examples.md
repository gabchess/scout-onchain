# Examples

## First run, no alert rules set

```bash
uv run python -m scout_portfolio_manager.reporting_html
```

Produces `scout-report.html` with the alerts panel showing the empty-state text ("No
alert rules are set. Use set_alert to add one.") and the technical-indicators panel
populated for every held asset, each labeled with the heuristic-disclosure string.

## Setting an alert, then watching

```python
from scout_portfolio_manager.host import default_host

host = default_host()
host.set_alert("ETH", "rsi_below", 30.0)
```

The next `watch` run's `check_alerts` step picks up the new rule from
`~/.scout/alerts.json` (or `ZPM_ALERTS_PATH`) and reports whether it fired, alongside its `stale` flag.

## Running under `/loop`

Point `/loop` at the same CLI invocation on a fixed interval. Each tick is a fresh
process: the chain re-runs, `scout-report.html` is overwritten, and any stored alert
rules are re-evaluated against the latest observed snapshot. Nothing schedules itself;
the loop is the only thing driving repetition.

## Custom report path

```bash
SCOUT_REPORT_PATH=/tmp/scout-watch.html uv run python -m scout_portfolio_manager.reporting_html
```
