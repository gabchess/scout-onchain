# Host matrix

Evidence labels describe what this repository can show. `CI` means a workflow blocks drift. `TEST` means offline coverage. `PACKAGE` means file inspection. `UNVERIFIED` needs a host or live smoke test.

| Capability | Claude Code plugin | Codex skills | Generic stdio MCP | Evidence |
|:--|:--|:--|:--|:--|
| Skill files | Root `skills/` | Generated `codex/plugins/` copy | Outside MCP | PACKAGE; generator has a CI drift check |
| Install command | `claude plugin marketplace add gabchess/scout-onchain` then `claude plugin install scout-portfolio@scout-portfolio-manager` | `codex plugin marketplace add gabchess/scout-onchain --ref v0.7.0`, `codex plugin add scout-portfolio --marketplace scout-portfolio-manager`, then `codex mcp add scout-portfolio -- uvx --from git+https://github.com/gabchess/scout-onchain@v0.7.0 scout-portfolio-manager` | One `mcpServers` entry running `uvx --from git+https://github.com/gabchess/scout-onchain@v0.7.0 scout-portfolio-manager` | Claude: LOCAL (`--plugin-dir`, 2026-09-16); Codex MCP and Cursor: UNVERIFIED |
| Config location | Plugin root `.mcp.json`; your shell env for keys | `~/.codex/config.toml` `[mcp_servers.scout-portfolio]` | Client `mcp.json` | PACKAGE |
| Portfolio tool set | Root `.mcp.json` runs `scout-portfolio-manager` | Attach the stdio route separately | `scout-portfolio-manager` (alias `zpm-mcp`) | CI; tool names and execution boundary are pinned; wheel smoke starts the server offline |
| Fixture default | Yes | Available after MCP attachment | Yes | CI; offline suite |
| Zerion API-key source | Yes | Available after MCP attachment | Yes | TEST; no current live call |
| Zerion x402 source | Only in your own MCP entry with `SCOUT_ENABLE_X402=1`; the plugin never sets it | Available after MCP attachment, with `SCOUT_ENABLE_X402=1` | Yes, with `SCOUT_ENABLE_X402=1` | TEST; SDK and budget hook run offline, live paid call unverified |
| Arc wallet reads | Yes | Available after MCP attachment | Yes | TEST; Zerion-shaped Arc fixture offline, live call unverified |
| Unsigned preparation on Arc | Accepted, live availability unverified | Available after MCP attachment | Accepted, live availability unverified | TEST; fixture envelopes and fake CLI refusals offline, no live Arc preparation |
| Local alert file | `~/.scout/alerts.json` or `ZPM_ALERTS_PATH` | Same, written by the attached MCP runtime | Same | TEST; alert path tests with a temp `HOME` |
| Trade execution | Absent | Absent | Absent | CI; runtime file and tool registry gate |
| Fresh archive install | Files present | Skills present | Package installs and lists all tools | LOCAL; tested in a clean Python 3.11 environment |
| Host UI discovery | Unverified | Unverified | Client-specific | Requires inspection inside each host |

## Plugin launch evidence (2026-09-16)

| Check | Host | Result |
|:--|:--|:--|
| `${VAR}` with the variable unset in plugin `.mcp.json` `env` | Claude Code 2.1.273 | Logs `mcp-config-invalid: Missing environment variables`, still starts the server, and passes the literal text `${VAR}` to the child |
| `${VAR:-}` with the variable unset | Claude Code 2.1.273 | No error; the child sees an empty value. Scout's `.mcp.json` uses this form |
| Scout plugin start with no Zerion variables | Claude Code 2.1.273, `--plugin-dir` | Connected; fixture |
| Scout plugin start with `ZERION_API_KEY` and `ZERION_WALLET_ADDRESS` set | Claude Code 2.1.273, `--plugin-dir` | Connected; no tool was called, so no Zerion request was made |
| Scout plugin start with a shell x402 key and wallet, no API key, no opt-in | Claude Code 2.1.273, `--plugin-dir` | Connected; stderr notice names `SCOUT_ENABLE_X402`; fixture |
| Shell environment inherited by a plugin MCP child | Claude Code 2.1.273 | Yes, the full shell environment, including `ZERION_X402_PRIVATE_KEY`, with or without an `env` block |
| Shell environment inherited by a configured MCP child | Codex CLI 0.154.0 | No. The child gets a fixed set (`HOME`, `PATH`, `SHELL`, `USER`, `LOGNAME`, `TMPDIR`, locale and SDK paths). Other variables arrive only through `env` or `env_vars` |

`claude plugin marketplace add gabchess/scout-onchain` tracks the default branch (`main`) unless you pass a ref. Tag-pinned installs use a ref.

`claude plugin validate .` is a release check; run it before tagging.

## Names

| Surface | Name |
|:--|:--|
| Repository | `scout-onchain` |
| Python package | `scout-portfolio-manager` |
| Console scripts | `scout-portfolio-manager`, `zpm-mcp` (same entry point) |
| MCP server | `scout-portfolio` |
| Plugin and marketplace | `scout-portfolio` from `scout-portfolio-manager` |

Claude Code is the primary packaged plugin. The Codex layout carries skills and metadata. It does not duplicate the Python runtime or root `.mcp.json` inside the generated plugin directory.

See [`START-HERE.md`](START-HERE.md) for install routes and [`CLAIMS.md`](CLAIMS.md) for claim status.
