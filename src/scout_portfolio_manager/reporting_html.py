"""Static, self-contained HTML report for Scout's full observe-through-alert chain.

No fetch calls, no external script/style references beyond what's inlined
here: this runs with no server behind it, unlike the interactive demo. The
demo's app.js is not reused (it fetches client-side); this module inlines
already-computed tool output server-side instead. Visual structure and CSS
classes are adapted from demo/zerion-portfolio-agent/static/{index.html,
styles.css} and inlined here.
"""

from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .host import ReadOnlyHost
from .mcp_server import build_host
from .zerion_api import ZerionConfigError

DEFAULT_REPORT_PATH = "scout-report.html"
X402_WATCH_BLOCKED = (
    "watch is disabled for x402 sources because one report makes multiple paid "
    "snapshot calls and Scout has no cumulative spend budget"
)


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _usd(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def _pct(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def _sign_class(value: Optional[float]) -> str:
    if value is None:
        return ""
    return "pos" if value >= 0 else "neg"


_STYLE = """
:root {
  --zr-navy: #06003C;
  --zr-original: #3232DC;
  --zr-digital: #2461ED;
  --zr-blue: #56ACFF;
  --zr-mint: #3FFDEE;
  --zr-peach: #FF7583;
  --zr-pink: #FFBDFF;
  --zr-grey: #F0F0F0;
  --positive: var(--zr-mint);
  --negative: var(--zr-peach);
  --font-sans: "Aeonik Pro", -apple-system, "Segoe UI", sans-serif;
  --bg: var(--zr-navy);
  --bg-raised: #0d0a52;
  --border: #241f5c;
  --text: var(--zr-grey);
  --mono: "SF Mono", ui-monospace, "Cascadia Code", Menlo, Consolas, monospace;
  --bg-inset: rgba(6, 0, 60, 0.55);
  --text-dim: rgba(240, 240, 240, 0.62);
  --attention: var(--zr-blue);
  --tint-mint-fill: rgba(63, 253, 238, 0.12);
  --tint-mint-line: rgba(63, 253, 238, 0.4);
  --tint-peach-fill: rgba(255, 117, 131, 0.12);
  --tint-peach-line: rgba(255, 117, 131, 0.4);
  --tint-digital-fill: rgba(36, 97, 237, 0.16);
  --tint-digital-line: rgba(36, 97, 237, 0.45);
  --tint-pink-fill: rgba(255, 189, 255, 0.12);
  --tint-pink-line: rgba(255, 189, 255, 0.4);
  --tint-blue-fill: rgba(86, 172, 255, 0.14);
  --tint-blue-line: rgba(86, 172, 255, 0.45);
  --tint-original-fill: rgba(50, 50, 220, 0.18);
  --tint-original-line: rgba(50, 50, 220, 0.5);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 15px/1.5 var(--font-sans);
}
.topbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 24px;
  padding: 18px 28px 10px;
}
.brand { display: flex; align-items: center; gap: 12px; }
.brand-mark {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  background: linear-gradient(135deg, var(--zr-mint), var(--zr-digital));
  clip-path: polygon(50% 10%, 90% 88%, 10% 88%);
}
.brand-text h1 { margin: 0; font-size: 18px; font-weight: 700; }
.brand-text p { margin: 0; font-size: 12.5px; color: var(--text-dim); }
.topbar-badges { display: flex; gap: 8px; }
.badge, .boundary, .pill, .conf {
  font: 600 10.5px/1 var(--mono);
  letter-spacing: 0.7px;
  text-transform: uppercase;
  padding: 5px 10px;
  border-radius: 999px;
  border: 1px solid;
  white-space: nowrap;
}
.badge-readonly {
  color: var(--positive);
  border-color: var(--tint-mint-line);
  background: var(--tint-mint-fill);
}
.badge-fixture {
  color: var(--attention);
  border-color: var(--tint-digital-line);
  background: var(--tint-digital-fill);
}
.pipeline {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 8px 28px 4px;
  padding: 10px 16px;
  background: var(--bg-inset);
  border: 1px solid var(--border);
  border-radius: 12px;
  font-family: var(--mono);
  font-size: 12.5px;
}
.stage { padding: 4px 10px; border-radius: 8px; }
.stage-on {
  background: var(--tint-original-fill);
  color: var(--zr-blue);
  border: 1px solid var(--tint-original-line);
}
.stage-off {
  background: transparent;
  color: var(--text-dim);
  border: 1px dashed var(--border);
  text-decoration: line-through;
}
.arrow { color: var(--text-dim); }
.arrow-cut { color: var(--negative); }
.pipeline-note { color: var(--text-dim); font-size: 11.5px; }
.grid {
  display: grid;
  grid-template-columns: minmax(380px, 1fr) minmax(420px, 1fr);
  gap: 16px;
  padding: 12px 28px 20px;
}
@media (max-width: 980px) { .grid { grid-template-columns: 1fr; } }
.col { display: flex; flex-direction: column; gap: 16px; }
.card {
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
}
.card-head {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
}
.card-head h2 { margin: 0; font-size: 15px; font-weight: 700; }
.card-body { padding: 16px 18px 18px; }
.boundary-observe {
  color: var(--zr-blue);
  border-color: var(--tint-blue-line);
  background: var(--tint-blue-fill);
}
.boundary-calculate {
  color: var(--zr-original);
  border-color: var(--tint-original-line);
  background: var(--tint-original-fill);
}
.boundary-propose {
  color: var(--zr-pink);
  border-color: var(--tint-pink-line);
  background: var(--tint-pink-fill);
}
.placeholder { color: var(--text-dim); font-size: 13.5px; }
table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
th {
  text-align: left;
  font: 600 10.5px/1.6 var(--mono);
  letter-spacing: 0.7px;
  text-transform: uppercase;
  color: var(--text-dim);
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
}
td {
  padding: 8px;
  border-bottom: 1px solid var(--border);
  font-family: var(--mono);
  text-align: left;
}
tr:last-child td { border-bottom: none; }
.subhead {
  margin: 16px 0 6px;
  font: 600 11px/1.4 var(--mono);
  letter-spacing: 0.8px;
  text-transform: uppercase;
  color: var(--text-dim);
}
.stat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}
.stat {
  background: var(--bg-inset);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 12px;
}
.stat .k {
  font: 600 10px/1.5 var(--mono);
  letter-spacing: 0.6px;
  text-transform: uppercase;
  color: var(--text-dim);
}
.stat .v { font-family: var(--mono); font-size: 15px; font-weight: 600; }
.pos { color: var(--positive); }
.neg { color: var(--negative); }
.callout {
  border-radius: 10px;
  padding: 12px 14px;
  margin: 10px 0;
  font-size: 13.5px;
  border: 1px solid;
}
.callout-fired {
  border-color: var(--tint-peach-line);
  background: var(--tint-peach-fill);
  color: var(--negative);
}
.callout-quiet {
  border-color: var(--tint-mint-line);
  background: var(--tint-mint-fill);
  color: var(--positive);
}
.disclosure {
  margin-top: 10px;
  font-size: 12px;
  color: var(--attention);
  border-top: 1px dashed var(--border);
  padding-top: 10px;
}
.safety-strip { padding: 12px 28px 18px; color: var(--text-dim); font-size: 12px; }
.built-on { margin: 0 0 8px; color: var(--text); font-size: 12.5px; font-weight: 600; }
.safety-strip code {
  font-family: var(--mono);
  color: var(--text);
  background: var(--bg-inset);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 3px 8px;
}
.safety-strip .dot { margin: 0 6px; color: var(--border); }
.asset-block { margin-bottom: 18px; }
.asset-block:last-child { margin-bottom: 0; }
.asset-block h3 { margin: 0 0 8px; font-size: 14px; }
"""


def _stat(label: str, value: str, sign_class: str = "") -> str:
    return (
        f'<div class="stat"><div class="k">{_esc(label)}</div>'
        f'<div class="v {sign_class}">{value}</div></div>'
    )


def _render_snapshot_panel(snapshot: Dict[str, Any]) -> str:
    holdings = snapshot.get("holdings", [])
    total = sum(h.get("value_usd", 0.0) for h in holdings)
    rows = "".join(
        f"<tr><td>{_esc(h['asset'])}</td><td>{h['quantity']:.6f}</td>"
        f"<td>{_usd(h['value_usd'])}</td></tr>"
        for h in holdings
    )
    stats = (
        _stat("Wallet", _esc(snapshot.get("wallet_address", "")))
        + _stat("Chain", _esc(snapshot.get("chain", "")))
        + _stat("Total value", _usd(total))
    )
    return f"""
    <section class="card">
      <div class="card-head">
        <h2>Portfolio snapshot</h2>
        <span class="boundary boundary-observe">observed</span>
      </div>
      <div class="card-body">
        <div class="stat-grid">{stats}</div>
        <table>
          <thead><tr><th>Asset</th><th>Quantity</th><th>Value</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </section>
    """


def _render_pnl_panel(pnl: Dict[str, Any]) -> str:
    results = pnl.get("results", [])
    total_usd = sum(r.get("total_usd", 0.0) for r in results)
    rows = "".join(
        _stat(
            r["asset"],
            f"{_usd(r['total_usd'])} ({_pct(r['return_pct'])})",
            _sign_class(r["total_usd"]),
        )
        for r in results
    )
    unknown = pnl.get("unknown", [])
    unknown_html = "".join(f'<p class="placeholder">{_esc(u)}</p>' for u in unknown)
    total_stat = _stat("Total", _usd(total_usd), _sign_class(total_usd))
    return f"""
    <section class="card">
      <div class="card-head">
        <h2>What&rsquo;s the PnL, Scout?</h2>
        <span class="boundary boundary-calculate">calculated</span>
      </div>
      <div class="card-body">
        <div class="stat-grid">{total_stat}{rows}</div>
        {unknown_html}
      </div>
    </section>
    """


def _render_asset_ta_block(asset: str, analysis: Dict[str, Any], window: Dict[str, Any]) -> str:
    indicators = analysis.get("indicators", {})
    range30 = indicators.get("range_30d") or {}
    stale = (analysis.get("freshness") or {}).get("stale")
    stale_html = '<p class="callout callout-fired">Price data is stale.</p>' if stale else ""
    unknown_html = "".join(
        f'<p class="placeholder">{_esc(u)}</p>' for u in analysis.get("unknown", [])
    )
    drawdown = indicators.get("drawdown_from_cost_basis_pct")
    range_low = _usd(range30.get("low"))
    range_high = _usd(range30.get("high"))
    rsi_14 = indicators.get("rsi_14")
    rsi_html = "n/a" if rsi_14 is None else _esc(rsi_14)
    stats = (
        _stat("SMA 20", _usd(indicators.get("sma_20")))
        + _stat("EMA 12", _usd(indicators.get("ema_12")))
        + _stat("RSI 14", rsi_html)
        + _stat("30d range", f"{range_low} to {range_high}")
        + _stat("Drawdown vs basis", _pct(drawdown), _sign_class(drawdown))
        + _stat("DCA window", _esc(window.get("label", "n/a")))
    )
    return f"""
        <div class="asset-block">
          <h3>{_esc(asset)}</h3>
          <div class="stat-grid">{stats}</div>
          {stale_html}
          {unknown_html}
        </div>
        """


def _render_ta_panel(
    analyses: Dict[str, Dict[str, Any]], windows: Dict[str, Dict[str, Any]]
) -> str:
    if not analyses:
        return """
    <section class="card">
      <div class="card-head">
        <h2>Technical indicators</h2>
        <span class="boundary boundary-calculate">calculated</span>
      </div>
      <div class="card-body"><p class="placeholder">No held assets to analyze.</p></div>
    </section>
        """
    disclosure = ""
    blocks = []
    for asset, analysis in analyses.items():
        disclosure = analysis.get("disclosure", disclosure)
        blocks.append(_render_asset_ta_block(asset, analysis, windows.get(asset, {})))
    disclosure_html = f'<p class="disclosure">{_esc(disclosure)}</p>' if disclosure else ""
    blocks_html = "".join(blocks)
    return f"""
    <section class="card">
      <div class="card-head">
        <h2>Technical indicators</h2>
        <span class="boundary boundary-calculate">calculated</span>
      </div>
      <div class="card-body">
        {blocks_html}
        {disclosure_html}
      </div>
    </section>
    """


def _render_alert_entry(entry: Dict[str, Any], css_class: str, prefix: str) -> str:
    return (
        f'<p class="callout {css_class}">{prefix}: {_esc(entry["asset"])} '
        f'{_esc(entry["kind"])} (observed {entry["observed_value"]}, '
        f'threshold {entry["threshold"]}, stale={entry["stale"]})</p>'
    )


def _render_alerts_panel(alerts: Dict[str, Any]) -> str:
    fired = alerts.get("fired", [])
    not_fired = alerts.get("not_fired", [])
    unknown = alerts.get("unknown", [])

    if not fired and not not_fired and not unknown:
        body = '<p class="placeholder">No alert rules are set. Use set_alert to add one.</p>'
    else:
        pieces = [_render_alert_entry(e, "callout-fired", "FIRED") for e in fired]
        pieces += [_render_alert_entry(e, "callout-quiet", "quiet") for e in not_fired]
        pieces += [f'<p class="placeholder">{_esc(u)}</p>' for u in unknown]
        body = "".join(pieces)

    not_financial_advice = alerts.get("not_financial_advice", "")
    advice_html = (
        f'<p class="disclosure">{_esc(not_financial_advice)}</p>' if not_financial_advice else ""
    )
    return f"""
    <section class="card">
      <div class="card-head">
        <h2>Alerts</h2>
        <span class="boundary boundary-calculate">calculated</span>
      </div>
      <div class="card-body">
        {body}
        {advice_html}
      </div>
    </section>
    """


def render_report(
    *,
    snapshot: Dict[str, Any],
    pnl: Dict[str, Any],
    analyses: Dict[str, Dict[str, Any]],
    windows: Dict[str, Dict[str, Any]],
    alerts: Dict[str, Any],
) -> str:
    """Return a complete, self-contained HTML document as a string.

    No fetch calls, no external script/style references beyond what's
    inlined here. All data is already computed by the caller (the watch
    skill's chain); this function performs no I/O and no network call of its
    own regardless of how the upstream host was constructed.
    """
    source_kind = _esc(snapshot.get("source", {}).get("kind", "fixture"))
    observed_at = _esc(snapshot.get("observed_at", ""))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Scout report</title>
<style>{_STYLE}</style>
</head>
<body>
  <header class="topbar">
    <div class="brand">
      <div class="brand-mark" aria-hidden="true"></div>
      <div class="brand-text">
        <h1>Scout</h1>
        <p>Portfolio report generated {observed_at}</p>
      </div>
    </div>
    <div class="topbar-badges">
      <span class="badge badge-readonly">NO TRADE</span>
      <span class="badge badge-fixture">{source_kind.upper()} DATA</span>
    </div>
  </header>

  <section class="pipeline" aria-label="Agent boundary pipeline">
    <span class="stage stage-on">observe</span>
    <span class="arrow">then</span>
    <span class="stage stage-on">calculate</span>
    <span class="arrow">then</span>
    <span class="stage stage-on">propose</span>
    <span class="arrow arrow-cut">stop</span>
    <span class="stage stage-off">execute unavailable</span>
    <span class="pipeline-note">
      Read-only. No execute, sign, or submit tool exists in this chain.
    </span>
  </section>

  <main class="grid">
    <div class="col">
      {_render_snapshot_panel(snapshot)}
      {_render_pnl_panel(pnl)}
    </div>
    <div class="col">
      {_render_ta_panel(analyses, windows)}
      {_render_alerts_panel(alerts)}
    </div>
  </main>

  <footer class="safety-strip">
    <p class="built-on">Generated by Scout's watch skill. One on-demand pass; not live.</p>
    <code>observe &ne; calculate &ne; propose &ne; approve &ne; execute &ne; verify</code>
    <span class="dot">&middot;</span> No wallet connect
    <span class="dot">&middot;</span> No signing
    <span class="dot">&middot;</span> No transaction submission
    <span class="dot">&middot;</span> No daemon, cron, or push
  </footer>
</body>
</html>
"""


def build_report(host: ReadOnlyHost) -> str:
    """Run the full observe-through-alert chain once and render the report."""
    if getattr(host.reader, "authorization_mode", None) == "x402":
        raise RuntimeError(X402_WATCH_BLOCKED)
    snapshot_result = host.get_portfolio_snapshot()
    snapshot = snapshot_result.get("snapshot", {})
    pnl = host.get_pnl()
    analyses: Dict[str, Dict[str, Any]] = {}
    windows: Dict[str, Dict[str, Any]] = {}
    for holding in snapshot.get("holdings", []):
        asset = holding["asset"]
        analyses[asset] = host.analyze_asset(asset)
        windows[asset] = host.dca_windows(asset)
    alerts = host.check_alerts()
    return render_report(
        snapshot=snapshot, pnl=pnl, analyses=analyses, windows=windows, alerts=alerts
    )


def main() -> int:
    """Build the report against the default fixtures and write it to disk.

    Invocation: `uv run python -m scout_portfolio_manager.reporting_html`.
    Output path: $SCOUT_REPORT_PATH, defaulting to ./scout-report.html.
    Source selection matches the MCP server's own build_host(): the read-only
    Zerion API when both its env vars are set, else $ZPM_FIXTURE_PATH, else
    the packaged fixture.
    """
    try:
        host = build_host()
    except ZerionConfigError as exc:
        raise SystemExit(f"scout-report: {exc}") from None
    report_html = build_report(host)
    output_path = Path(os.environ.get("SCOUT_REPORT_PATH", DEFAULT_REPORT_PATH))
    output_path.write_text(report_html)
    print(f"wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
