# Security

## Product boundary

- The default fixture and host are read-only.
- The MCP server registers observation, calculation, parsing, and preview tools only.
- No component connects a wallet, signs, submits, or executes a transaction.
- The optional Zerion adapter performs a read-only aggregate portfolio request; it does not expose an execution rail.
- The optional x402 mode (`ZERION_X402_PRIVATE_KEY`) settles per-request data fees from a dedicated payment wallet. It is the only signing the product does, it is capped client-side before signing (default `$0.05` per call), and the observed wallet never signs. Treat the payment wallet key as a hot secret: dedicated wallet, minimal balance.
- A preview is a proposal and must not be represented as a completed transaction.
- `analyze_asset`, `dca_windows`, `set_alert`, and `check_alerts` are read-only; their output is heuristic, not investment advice.

## Secrets and data

- Never commit or paste API keys, private keys, seed phrases, or wallet secrets into source, fixtures, prompts, logs, or issue reports.
- Configure API credentials through a customer-controlled secret manager or environment supplied by the host.
- Contract validation rejects unknown fields, reducing the chance of accidentally carrying secret-bearing payloads.
- Fixture data is synthetic. Do not replace it with personal wallet data in tests or examples.

## Reporting a vulnerability

Do not open a public issue containing credentials, personal wallet data, or an exploitable vulnerability. Contact the repository maintainers through the private security channel configured for the deployment or organization that runs this project. If no private channel has been provided, open a minimal public issue requesting a security contact without including sensitive details.

This repository does not promise a response time or a supported production service. See [`SUPPORT.md`](SUPPORT.md) for general questions.
