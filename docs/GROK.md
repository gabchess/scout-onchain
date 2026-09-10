# Grok compatibility

The [xAI plugin marketplace](https://github.com/xai-org/plugin-marketplace) accepts catalog PRs for **Grok Build**. Scout uses the accepted Claude-compatible `.claude-plugin/plugin.json`, `skills/` and root `.mcp.json` layout. Its plugin-root paths use the plain `${CLAUDE_PLUGIN_ROOT}` token supported by the Grok loader.

After obtaining a reviewed Scout source checkout, install it with:

```sh
grok plugin install /absolute/path/to/scout-onchain --trust
```

Inspect the source first: trusting a plugin permits its declared local MCP process. The process requires Python 3.11+ and `uv`, resolves dependencies from `uv.lock`, and starts in fixture mode without provider credentials. It declares one focused stdio MCP server and no lifecycle hooks. Optional Zerion access needs separate operator configuration described in START-HERE.md and ZERION-PREPARATION.md.

## Grok Bot validation

Grok Bot has a separate Plugins marketplace. Its [skills documentation](https://docs.x.ai/grok-bot/skills-routines-and-automations) describes packaged skills and per-Bot enablement. [Shared Bots](https://docs.x.ai/grok-bot/bots) distribute a profile and enabled skills through a public link. Neither page establishes that a Grok Build catalog PR publishes a plugin to Grok Bot.

The desktop surface inspected on 2026-09-10 exposes Marketplace → Plugins → Your plugins. It shows installed connectors and local private skills. No repository import or public submission control was found in that view. Bot installation and a successful Bot tool call remain unverified. A Build catalog PR must not be described as achieving Bot distribution.

Use Scout as the first distribution experiment. Keep a future Zerion-branded contribution paused until the Bot route is established and tested. The portable source and fixture-only acceptance prompts in `evals/knowledge-cases.json` are ready for that test. A profile alone does not supply Scout's MCP runtime.
