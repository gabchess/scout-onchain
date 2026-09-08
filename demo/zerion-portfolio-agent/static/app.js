/* Renders the fixture-backed demo. Technical detail stays collapsed. */

const $ = (sel) => document.querySelector(sel);

const usd = (n) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD" });

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];
const fmtMonthDay = (iso) => {
  const d = new Date(iso);
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`;
};

const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

const esc = (s) =>
  String(s).replace(
    /[&<>"']/g,
    (c) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[c],
  );

async function getJSON(path) {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`${path} responded ${res.status}`);
  }
  return res.json();
}

async function postJSON(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

const details = (summary, innerHtml) => `
  <details class="details">
    <summary>${esc(summary)}</summary>
    ${innerHtml}
  </details>`;

/* ---------- Snapshot (observe) ---------- */

function renderSnapshot(data) {
  const el = $("#snapshot-body");
  if (data.status !== "ok") {
    el.innerHTML = `<p class="placeholder">Snapshot unavailable: ${esc(
      data.error?.message || data.error || "unknown error",
    )}</p>`;
    return;
  }
  const s = data.snapshot;
  $("#source-badge").textContent =
    s.source.kind === "fixture" ? "Fixture data" : cap(s.source.kind);

  const total = s.holdings.reduce((acc, h) => acc + h.value_usd, 0);

  const holdingsRows = s.holdings
    .map(
      (h) => `<tr>
        <td>${esc(h.asset)}</td>
        <td class="num">${h.quantity}</td>
        <td class="num">${usd(h.value_usd)}</td>
      </tr>`,
    )
    .join("");

  const txRows = s.transactions
    .map(
      (t) => `<tr>
        <td>${esc(t.kind)}</td>
        <td>${esc(t.asset)}</td>
        <td class="num">${t.quantity}</td>
        <td class="num">${usd(t.value_usd)}</td>
        <td class="num">${usd(t.fee_usd)}</td>
        <td>${esc(t.occurred_at.slice(0, 10))}</td>
      </tr>`,
    )
    .join("");

  el.innerHTML = `
    <div class="stat-hero">
      <div class="num">${usd(total)}</div>
      <div class="lbl">One wallet, one snapshot.</div>
    </div>
    ${details(
      "Details",
      `
      <div class="kv-row">
        <div class="kv"><div class="k">Wallet</div><div class="v">${esc(s.wallet_address)}</div></div>
        <div class="kv"><div class="k">Chain</div><div class="v">${esc(cap(s.chain))}</div></div>
        <div class="kv"><div class="k">Observed</div><div class="v">${fmtMonthDay(s.observed_at)}</div></div>
        <div class="kv"><div class="k">Source</div><div class="v">${esc(s.source.kind)} &middot; ${esc(s.source.locator)}</div></div>
      </div>
      <table>
        <thead><tr><th>Asset</th><th class="num">Quantity</th><th class="num">Value</th></tr></thead>
        <tbody>${holdingsRows}</tbody>
      </table>
      <div class="subhead">Transaction ledger</div>
      <table>
        <thead><tr><th>Kind</th><th>Asset</th><th class="num">Qty</th><th class="num">Value</th><th class="num">Fee</th><th>Date</th></tr></thead>
        <tbody>${txRows}</tbody>
      </table>`,
    )}`;
}

/* ---------- PnL (calculate) ---------- */

function renderPnl(data, snapshot) {
  const el = $("#pnl-body");
  if (data.status !== "ok") {
    el.innerHTML = `<p class="placeholder">PnL unavailable: ${esc(
      data.error?.message || data.error || "unknown error",
    )}</p>`;
    return;
  }
  if (!data.results.length) {
    el.innerHTML = `<p class="placeholder">No PnL to show yet.</p>`;
    return;
  }
  const cls = (n) => (n >= 0 ? "pos" : "neg");
  const sign = (n) => (n >= 0 ? "+" : "");
  const snap = snapshot?.status === "ok" ? snapshot.snapshot : null;

  const blocks = data.results
    .map((r) => {
      const buys = (snap?.transactions || []).filter(
        (t) => t.asset === r.asset && t.kind === "buy",
      );
      const paid = buys.reduce((acc, t) => acc + t.value_usd, 0);
      const holding = (snap?.holdings || []).find((h) => h.asset === r.asset);
      const worthNow = holding ? holding.value_usd : null;

      const detailRows = `
        <div class="formula"><b>How this was computed:</b> ${esc(r.formula)}</div>
        ${
          buys.length
            ? `<div class="formula">Bought ${esc(r.asset)} for ${usd(paid)} on ${fmtMonthDay(buys[0].occurred_at)}.</div>`
            : ""
        }
        <div class="formula">Confidence: ${esc(r.confidence)}. Valued as of ${fmtMonthDay(r.valuation_at)}.</div>
        ${r.warnings.length ? `<p class="callout callout-question">${esc(r.warnings.join("; "))}</p>` : ""}`;

      if (paid === 0 || worthNow == null) {
        return `<p class="placeholder">Not enough data for ${esc(r.asset)}.</p>`;
      }

      return `
        <div class="pnl-hero">
          <div class="pnl-num"><div class="num">${usd(paid)}</div><div class="lbl">Paid</div></div>
          <div class="pnl-num"><div class="num">${usd(worthNow)}</div><div class="lbl">Worth now</div></div>
          <div class="pnl-num"><div class="num ${cls(r.return_pct)}">${sign(r.return_pct)}${r.return_pct}%</div><div class="lbl">Return</div></div>
        </div>
        <p class="asof">as of ${fmtMonthDay(r.valuation_at)}</p>
        ${details("Details", detailRows)}`;
    })
    .join("<hr class='rule'/>");

  const unknown = data.unknown.length
    ? `<p class="placeholder">${esc(data.unknown.join("; "))}</p>`
    : "";
  el.innerHTML = blocks + unknown;
}

/* ---------- DCA agent (propose / approve) ---------- */

function plainChips(intent) {
  const order = ["asset", "amount_usd", "chain", "schedule"];
  const items = order
    .map((name) => {
      const val = intent[name];
      if (val == null || val === "") return null;
      if (name === "amount_usd") return usd(val);
      if (name === "chain" || name === "schedule") return cap(val);
      return val;
    })
    .filter(Boolean);
  return `<div class="chip-row">${items
    .map((v) => `<span class="chip-plain">${esc(v)}</span>`)
    .join("")}</div>`;
}

function renderDca(text, parseRes, previewRes) {
  const el = $("#dca-result");

  if (parseRes.status === "needs_clarification") {
    el.innerHTML = `
      <p class="user-line">&ldquo;${esc(text)}&rdquo;</p>
      <p class="callout callout-question">${esc(parseRes.question)}</p>
      ${details(
        "Details",
        `<div class="mono-id">boundary: ${esc(parseRes.boundary)}</div>
         <div class="mono-id">missing: ${esc(parseRes.missing.join(", "))}</div>`,
      )}`;
    return;
  }

  const p = previewRes.preview;
  el.innerHTML = `
    <p class="user-line">&ldquo;${esc(text)}&rdquo;</p>
    ${plainChips(previewRes.intent)}
    <p class="approval-line">Approval required.</p>
    <p class="proposal-disclosure">Analysis, not financial advice.</p>
    ${details(
      "Details",
      `<div class="intent-grid">
        <div class="field"><div class="k">Expected output</div><div class="v">${p.expected_output} ${esc(p.asset)}</div></div>
        <div class="field"><div class="k">Fees</div><div class="v">${usd(p.fees_usd)}</div></div>
        <div class="field"><div class="k">Slippage</div><div class="v">${p.slippage_pct}%</div></div>
        <div class="field"><div class="k">Max fee</div><div class="v">${usd(p.max_fee_usd)}</div></div>
        <div class="field"><div class="k">Quote expiry</div><div class="v">${esc(p.quote_expiry)}</div></div>
        <div class="field"><div class="k">Preview ID</div><div class="v">${esc(p.preview_id.slice(0, 13))}&hellip;</div></div>
      </div>
      <ul class="assumed">
        ${previewRes.assumed.map((a) => `<li>${esc(a)}</li>`).join("")}
      </ul>
      <div class="preview-note">${esc(previewRes.note)}</div>`,
    )}`;
}

async function runDca(text) {
  const el = $("#dca-result");
  el.innerHTML = `<p class="loading">Parsing&hellip;</p>`;
  const parseRes = await postJSON("/api/dca/parse", { text });
  if (parseRes.status === "error") {
    el.innerHTML = `<p class="placeholder">${esc(parseRes.error)}</p>`;
    return;
  }
  const previewRes =
    parseRes.status === "ready"
      ? await postJSON("/api/dca/preview", { text })
      : null;
  renderDca(text, parseRes, previewRes);
}

/* ---------- Analysis (calculate), verdict sourced from dca_windows' label ---------- */

function verdictText(label, asset) {
  return `${asset} matches the ${label} rule set.`;
}

function renderTa(analyzeData, windowData) {
  const el = $("#ta-body");
  if (analyzeData.status !== "ok") {
    el.innerHTML = `<p class="placeholder">Analysis unavailable: ${esc(
      analyzeData.error?.message || analyzeData.error || "unknown error",
    )}</p>`;
    return;
  }
  const ind = analyzeData.indicators || {};
  const range = ind.range_30d;
  const rangeText =
    range != null ? `${usd(range.low)} to ${usd(range.high)}` : "n/a";
  const label = windowData?.status === "ok" ? windowData.label : null;
  const asset = analyzeData.asset;

  const verdict = label
    ? verdictText(label, asset)
    : `Not enough data on ${esc(asset)} yet.`;

  const staleHtml = analyzeData.freshness?.stale
    ? `<p class="callout callout-question">Price data is stale (last observed ${esc(
        analyzeData.freshness.last_price_date,
      )}).</p>`
    : "";
  const unknownHtml = analyzeData.unknown.length
    ? `<p class="callout callout-question">${esc(analyzeData.unknown.join("; "))}</p>`
    : "";

  el.innerHTML = `
    <p class="verdict">${esc(verdict)}</p>
    ${details(
      "Details",
      `<div class="ta-stats">
        <div class="stat"><div class="k">SMA 20</div><div class="v">${
          ind.sma_20 != null ? usd(ind.sma_20) : "n/a"
        }</div></div>
        <div class="stat"><div class="k">EMA 12</div><div class="v">${
          ind.ema_12 != null ? usd(ind.ema_12) : "n/a"
        }</div></div>
        <div class="stat"><div class="k">RSI 14</div><div class="v">${
          ind.rsi_14 != null ? ind.rsi_14 : "n/a"
        }</div></div>
        <div class="stat"><div class="k">30d range</div><div class="v">${rangeText}</div></div>
      </div>
      ${staleHtml}${unknownHtml}
      <div class="formula">${esc(analyzeData.disclosure)}</div>`,
    )}`;
}

async function loadTa() {
  const el = $("#ta-body");
  el.innerHTML = `<p class="loading">Loading&hellip;</p>`;
  try {
    const [analyzeData, windowData] = await Promise.all([
      getJSON("/api/analyze"),
      getJSON("/api/dca-windows"),
    ]);
    renderTa(analyzeData, windowData);
  } catch (err) {
    el.innerHTML = `<p class="placeholder">Analysis unavailable: ${esc(err.message)}</p>`;
  }
}

/* ---------- DCA Windows (propose) ---------- */

function renderDcaWindow(data) {
  const el = $("#dca-windows-body");
  if (data.status !== "ok") {
    el.innerHTML = `<p class="placeholder">DCA context unavailable: ${esc(
      data.error?.message || data.error || "unknown error",
    )}</p>`;
    return;
  }
  const staleHtml = data.freshness?.stale
    ? `<p class="callout callout-question">Based on stale price data.</p>`
    : "";
  const amountRow =
    data.suggested_amount_usd != null
      ? `<div class="field"><div class="k">Suggested amount</div><div class="v">${usd(
          data.suggested_amount_usd,
        )}</div></div>`
      : "";
  el.innerHTML = `
    <div class="window-hero">
      <div class="window-word window-${esc(data.label)}">${esc(cap(data.label))}</div>
      <div class="lbl">for ${esc(data.asset)}, ${esc(data.risk_profile)} risk</div>
    </div>
    ${details(
      "Details",
      `<div class="intent-grid">
        <div class="field"><div class="k">Sizing fraction</div><div class="v">${data.sizing_fraction}</div></div>
        ${amountRow}
      </div>
      <div class="formula">${esc(data.rationale)}</div>
      <div class="formula">${esc(data.sensitivity_note)}</div>
      ${staleHtml}`,
    )}`;
}

async function loadDcaWindow() {
  const el = $("#dca-windows-body");
  el.innerHTML = `<p class="loading">Loading&hellip;</p>`;
  const riskProfile = $("#risk-profile-select").value;
  try {
    const data = await getJSON(
      `/api/dca-windows?risk_profile=${encodeURIComponent(riskProfile)}`,
    );
    renderDcaWindow(data);
  } catch (err) {
    el.innerHTML = `<p class="placeholder">DCA context unavailable: ${esc(err.message)}</p>`;
  }
}

/* ---------- Alerts (calculate) ---------- */

function renderAlerts(data) {
  const el = $("#alerts-body");
  if (data.status !== "ok") {
    el.innerHTML = `<p class="placeholder">Alerts unavailable: ${esc(
      data.error?.message || data.error || "unknown error",
    )}</p>`;
    return;
  }
  const { fired, not_fired, unknown } = data;

  const mainLine = fired.length
    ? `${fired.length} alert${fired.length === 1 ? "" : "s"} firing.`
    : "No alerts fired.";

  if (!fired.length && !not_fired.length && !unknown.length) {
    el.innerHTML = `<p class="verdict">No alerts set.</p>`;
    return;
  }

  const row = (e, kind) => `<div class="alert-row ${kind}">
      <span class="alert-tag">${kind === "fired" ? "fired" : "quiet"}</span>
      <span>${esc(e.asset)} &middot; ${esc(e.kind)}${e.stale ? " &middot; stale" : ""}</span>
    </div>`;
  const rows =
    fired.map((e) => row(e, "fired")).join("") +
    not_fired.map((e) => row(e, "not-fired")).join("");
  const unknownHtml = unknown.length
    ? `<p class="callout callout-question">${esc(unknown.join("; "))}</p>`
    : "";

  el.innerHTML = `
    <p class="verdict">${esc(mainLine)}</p>
    ${details("Details", `${rows}${unknownHtml}`)}`;
}

async function loadAlerts() {
  const el = $("#alerts-body");
  el.innerHTML = `<p class="loading">Loading&hellip;</p>`;
  try {
    const data = await getJSON("/api/alerts");
    renderAlerts(data);
  } catch (err) {
    el.innerHTML = `<p class="placeholder">Alerts unavailable: ${esc(err.message)}</p>`;
  }
}

/* ---------- Wire up ---------- */

$("#dca-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("#dca-input").value.trim();
  if (text) runDca(text);
});

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    $("#dca-input").value = chip.dataset.example;
    runDca(chip.dataset.example);
  });
});

$("#risk-profile-select").addEventListener("change", loadDcaWindow);

loadTa();
loadDcaWindow();
loadAlerts();

Promise.allSettled([getJSON("/api/snapshot"), getJSON("/api/pnl")]).then(
  ([snapshotResult, pnlResult]) => {
    const snapshot =
      snapshotResult.status === "fulfilled" ? snapshotResult.value : null;

    if (snapshotResult.status === "fulfilled") {
      renderSnapshot(snapshot);
    } else {
      $("#snapshot-body").innerHTML =
        `<p class="placeholder">Snapshot unavailable: ${esc(
          snapshotResult.reason?.message || String(snapshotResult.reason),
        )}</p>`;
    }

    if (pnlResult.status === "fulfilled") {
      renderPnl(pnlResult.value, snapshot);
    } else {
      $("#pnl-body").innerHTML = `<p class="placeholder">PnL unavailable: ${esc(
        pnlResult.reason?.message || String(pnlResult.reason),
      )}</p>`;
    }
  },
);
