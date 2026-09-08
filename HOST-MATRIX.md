# Host matrix

Evidence labels describe what this repository can show. `CI` means a workflow blocks drift. `TEST` means offline coverage. `PACKAGE` means file inspection. `UNVERIFIED` needs a host or live smoke test.

| Capability | Claude Code plugin | Codex skills | Generic stdio MCP | Evidence |
|:--|:--|:--|:--|:--|
| Skill files | Root `skills/` | Generated `codex/plugins/` copy | Outside MCP | PACKAGE; generator has a CI drift check |
| Portfolio tool set | Root `.mcp.json` | Attach the stdio route separately | `zpm-mcp` | CI; tool names and execution boundary are pinned |
| Fixture default | Yes | Available after MCP attachment | Yes | CI; offline suite |
| Zerion API-key source | Yes | Available after MCP attachment | Yes | TEST; no current live call |
| Zerion x402 source | Yes | Available after MCP attachment | Yes | TEST; SDK and budget hook run offline, live paid call unverified |
| Local alert file | `.scout/alerts.json` | Written by attached MCP runtime | `.scout/alerts.json` | CI; alert tests |
| Trade execution | Absent | Absent | Absent | CI; runtime file and tool registry gate |
| Fresh archive install | Files present | Skills present | Package installs and lists all tools | LOCAL; tested in a clean Python 3.11 environment |
| Host UI discovery | Unverified | Unverified | Client-specific | Requires inspection inside each host |

Claude Code is the primary packaged plugin. The Codex layout carries skills and metadata. It does not duplicate the Python runtime or root `.mcp.json` inside the generated plugin directory.

See [`START-HERE.md`](START-HERE.md) for install routes and [`CLAIMS.md`](CLAIMS.md) for claim status.
