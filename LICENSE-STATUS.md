# License status

Rights position for the 0.3.x line. The license body itself lives in [`LICENSE.md`](LICENSE.md); this file says what it covers and what it does not.

## What the license covers

Scout Portfolio Manager ships under the MIT License, copyright 2026 Zerion Portfolio Manager contributors. That grant covers this repository's own source, docs, fixtures, and manifests: use, copy, modify, merge, publish, distribute, sublicense, and sell, per the terms in `LICENSE.md`.

## What the license does not cover

- **Zerion API.** Live API use is governed entirely by Zerion's own terms (https://zerion.io/terms), not by this license. See [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md), section "Zerion API terms (optional adapter)".
- **Zerion brand tokens.** The demo's color and typography values come from https://design.zerion.io and carry no endorsement. See [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md), section "Zerion brand tokens (demo only)".
- **Fixture data provenance.** `fixtures/portfolio.json` and `fixtures/price_history.json` are synthetic bundled test data, never live market or wallet data. See [`DATA-AND-PRIVACY.md`](DATA-AND-PRIVACY.md).
- **Third-party Python dependencies.** Each carries its own MIT license, listed in [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md).

## No warranty of financial advice

MIT ships the software "AS IS", without warranty of any kind. On top of that, this product's own docs state the limit directly: analysis output "is heuristic, not investment advice" ([`SECURITY.md`](SECURITY.md)), and "This is analysis, not financial advice." ([`CHANGELOG.md`](CHANGELOG.md), 0.3.0, `dca_windows`). No production availability, endpoint compatibility, or support SLA is claimed ([`SUPPORT.md`](SUPPORT.md), `RELEASE-MANIFEST.json` `known_limits`).
