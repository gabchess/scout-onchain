# Shock Lab — SIMULATED marketer demo for Scout v0.5.0

A self-contained, one-screen web demo of Scout's honest v0.5.0 core: portfolio
concentration over gross observed holdings, declared price-shock scenarios with
visible freshness, and optional **unsigned** action preparation.

Everything is **SIMULATED** from a synthetic fixture embedded in `index.html`.
No live Zerion, no API keys, no signing, no broadcasting — Scout v0.5.0 exposes
no execute/sign/submit tools, and neither does this page.

## How to open

No build step, no dependencies. Any of these works from this folder
(`demo/shock-lab/`):

```bash
# Option A: Python
python -m http.server 8000
# then open http://localhost:8000

# Option B: Bun
bunx serve .

# Option C: no server at all
open index.html        # macOS
xdg-open index.html    # Linux
```

## Click path

1. Read the title banner: **Scout v0.5 · Shock Lab · SIMULATED**.
2. The wallet field is prefilled with a fixture address — click
   **Load fixture snapshot** (any pasted text still loads the bundled fixture;
   nothing is sent anywhere).
3. See the concentration heatmap and callout (~80% of gross observed value in
   one token, plus HHI).
4. Drag the shock slider or hit the **−30% / −50%** presets — the simulated
   PnL line and freshness badge update live.
5. Click **Prep unsigned action** — an unsigned calldata preview appears under
   a large **CANNOT SIGN · CANNOT BROADCAST** lock.
6. The end card links to the
   [Scout v0.5.0 release](https://github.com/gabchess/scout-onchain/releases/tag/v0.5.0).

## What this demo does NOT do

- No live portfolio reads (fixture only; freshness of the fixture is shown).
- No signing, no broadcasting, no review sessions.
- No push alerts, WalletConnect, or automated buys (Scout never claims these —
  see the repo's `CLAIMS.md`).
- No real pricing: all values are synthetic fixture numbers.
