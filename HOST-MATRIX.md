# Host matrix

Evidence labels describe what this repository can show. `CI` means a workflow blocks drift. `TEST` means offline coverage. `PACKAGE` means file inspection. `UNVERIFIED` needs a host or live smoke test.

| Capability | Claude Code plugin | Codex skills | Generic stdio MCP | Evidence |
|:--|:--|:--|:--|:--|
| Skill files | Root `skills/` | Generated `codex/plugins/` copy | Outside MCP | PACKAGE; generator has a CI drift check |
| Portfolio tool set | Root `.mcp.json` | Attach the stdio route separately | `zpm-mcp` | CI; tool names and execution boundary are pinned |
| Fixture default | Yes | Available after MCP attachment | Yes | CI; offline suite |
| Zerion API-key source | Yes | Available after MCP attachment | Yes | TEST; no current live call |
| Zerion x402 source | Yes | Available after MCP attachment | Yes | TEST; SDK and budget hook run offline, live paid call unverified |
| Arc wallet reads | Yes | Available after MCP attachment | Yes | TEST; Zerion-shaped Arc fixture offline, live call unverified |
| Unsigned preparation on Arc | Accepted, live availability unverified | Available after MCP attachment | Accepted, live availability unverified | TEST; fixture envelopes and fake CLI refusals offline, no live Arc preparation |
| Local alert file | `.scout/alerts.json` | Written by attached MCP runtime | `.scout/alerts.json` | CI; alert tests |
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

Claude Code is the primary packaged plugin. The Codex layout carries skills and metadata. It does not duplicate the Python runtime or root `.mcp.json` inside the generated plugin directory.

See [`START-HERE.md`](START-HERE.md) for install routes and [`CLAIMS.md`](CLAIMS.md) for claim status.
