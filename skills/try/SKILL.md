---
name: try
description: Runs a fixed zero-key tour of Scout on the bundled synthetic portfolio, covering risk, PnL, and a DCA proposal, then shows how to connect your own wallet. Use when the user wants to try, demo, or tour Scout.
---

# Try Scout

If the Scout tools (`get_portfolio_risk`, `get_pnl`, `preview_dca`) are missing, stop. Tell the user to run `uv --version`, install uv if that fails, and then restart the host so the Scout MCP server starts.

## Scope

A short, fixed tour on the bundled synthetic fixture. It needs no key and no wallet. Run the steps in order and make no other tool calls. At most 4 tool calls.

## Rules

- Start every block with `Source: bundled synthetic fixture (not your wallet)`.
- After step 1, read `source.kind`. If it is not `fixture`, stop the tour. Say that Scout is already connected to a live source, so this tour would not show the fixture, and that the regular Scout skills handle live questions.
- Never sign, submit, or execute anything. Scout has no tool that can.
- Never ask for a key, seed phrase, or private key.
- If the user pastes anything that looks like a key or secret, do not repeat it. Tell them to rotate that key now, because it is in the chat transcript, and point them to the host config in "Use your own wallet".

## Tour

1. Call `get_portfolio_risk` with `{"shock_pct": -30}`. Report the largest exposure (`top_exposure`: asset and weight) and the stress loss (`scenario.change_usd` for a uniform -30% shock).
2. Call `get_pnl` with `{}`. Report realized and unrealized PnL per asset.
3. Call `preview_dca` with `{"text": "Buy $50 of ETH weekly on base from wallet:tour-wallet to rail:tour-rail"}`. Report the proposal and quote both fields exactly: `approval_state=required` and `execution_available=false`. Then say: "Proposal only. Scout cannot sign or send." Say that the quote uses fixture placeholder prices, listed in `assumed`.
4. Optional: call `search_defi_knowledge` with `{"query": "<one term from step 1, such as concentration risk>", "limit": 1}` and give the one-line definition with its source link.

## Close: Use your own wallet

Scout reads your wallet when the host starts it with `ZERION_API_KEY` and `ZERION_WALLET_ADDRESS`. Set them in host config, never in chat:

- Claude Code plugin: export both variables in the shell that launches Claude Code, then restart it.
- Codex: add them under `[mcp_servers.scout-portfolio]` in `~/.codex/config.toml` as `env_vars = ["ZERION_API_KEY", "ZERION_WALLET_ADDRESS"]`, then restart.
- Cursor and other stdio clients: add an `env` block with both variables to the Scout entry in the client's MCP config, then restart.

End with this line: "Do not paste keys into this chat."
