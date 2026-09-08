# Host matrix

Evidence labels describe what this repository can show. `CI` means a workflow blocks drift. `TEST` means offline coverage. `PACKAGE` means file inspection. `UNVERIFIED` needs a host or live smoke test.

| Capability | Claude Code plugin | Codex skills | Generic stdio MCP | Evidence |
|:--|:--|:--|:--|:--|
| Skill files | Root `skills/` | Generated `codex/plugins/` copy | Outside MCP | PACKAGE; generator has a CI drift check |
| Eight MCP tools | Root `.mcp.json` | Attach the stdio route separately | `zpm-mcp` | CI; tool names and import boundary are pinned |
| Fixture default | Yes | Available after MCP attachment | Yes | CI; offline suite |
| Zerion API-key source | Yes | Available after MCP attachment | Yes | TEST; no current live call |
| Zerion x402 source | Yes | Available after MCP attachment | Yes | TEST; real SDK builds offline, live paid call unverified |
| Local alert file | `.scout/alerts.json` | Written by attached MCP runtime | `.scout/alerts.json` | CI; alert tests |
| Trade execution | Absent | Absent | Absent | CI; AST graph and tool registry gate |
| Fresh-host activation | Unverified | Unverified | Unverified | Requires host-specific smoke evidence |

Claude Code is the primary packaged plugin. The Codex layout carries skills and metadata. It does not duplicate the Python runtime or root `.mcp.json` inside the generated plugin directory.

See [`START-HERE.md`](START-HERE.md) for install routes and [`CLAIMS.md`](CLAIMS.md) for claim status.
