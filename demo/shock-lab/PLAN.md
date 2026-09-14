# Shock Lab — plan

## Goal

A one-screen SIMULATED marketer demo that shows Scout v0.5.0's honest core in
under a minute: concentration risk, declared shock scenarios with visible
freshness, and unsigned-only action preparation — ending on the v0.5.0 release
link.

## MVP (what shipped)

- Single `index.html`, plain HTML/CSS/JS, zero dependencies, zero build.
- Synthetic fixture embedded in the page (mirrors `fixtures/portfolio.json`
  shape: `observed_at`, `source.kind: "fixture"`, holdings).
- Click path: title → prefilled wallet paste → concentration heatmap +
  ~80%-in-one-token callout + HHI → shock slider (−30%/−50% presets) driving a
  simulated PnL line and freshness badge → unsigned prep preview with a giant
  CANNOT SIGN / CANNOT BROADCAST lock → end card linking the v0.5.0 release.
- SIMULATED / fixture labels on the sticky ribbon, header, and every section.
- Shock math matches `advisory.portfolio_risk`: uniform shock over gross
  observed holdings; HHI as the concentration figure.

## Outs (deliberately not built)

- No live Zerion (API-key or x402) wiring — fixture only, per AGENTS.md.
- No signing/broadcast of any kind; the prep preview is synthetic calldata
  that is invalid on every chain.
- No framework, bundler, or package.json — plain HTML keeps the demo
  auditable and instantly runnable.
- No real Vista/Scout pricing, no push alerts, no WalletConnect claims.
- No multi-wallet or multi-chain UI; one fixture wallet tells the story.
