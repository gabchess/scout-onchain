# zerion-adapter provenance

## Source

The adapter code is original to this repository. It targets Zerion's public `GET /wallets/{addr}/positions/` and `GET /wallets/{addr}/transactions/` contracts at `api.zerion.io`. The optional x402 transport uses the separately installed x402 Python SDK.

## Current limits

Transaction pagination stops at `ZerionAPIConfig.max_pages`, which defaults to 20 pages of 100. The quantity parser accepts a bare number or a `{"float": ...}` object. Automated tests use injected responses and make no live Zerion call.

x402 has a per-payment cap and no cumulative Scout budget. Its SDK contract is tested offline. Live paid behavior remains unverified in this repository.

## Evidence boundary

This notice states source and test scope. It does not prove current provider behavior.
