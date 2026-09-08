"""Generate or verify the Codex skill layout from canonical plugin sources.

Canonical sources:
  - `.claude-plugin/plugin.json`      -> Codex plugin manifest
  - `.claude-plugin/marketplace.json` -> Codex marketplace catalog
  - `skills/`                         -> Codex skill tree
  - `agents/` (when present)          -> Codex agent tree

The generated Codex plugin carries skills and metadata. Scout's Python/MCP
runtime stays at the repository root and is attached through a separate stdio
MCP route documented in START-HERE.md.

Usage:
    python scripts/build_host_layouts.py
    python scripts/build_host_layouts.py --check
    python scripts/build_host_layouts.py --check /path/repo
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

EXCLUDED_PARTS = {"__pycache__", ".DS_Store"}


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return payload


def _plugin_name(root: Path) -> str:
    plugin = _load_json(root / ".claude-plugin" / "plugin.json")
    name = plugin.get("name")
    if not isinstance(name, str) or not name:
        raise SystemExit("`.claude-plugin/plugin.json` is missing a string `name` field")
    return name


def _json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, indent=2) + "\n").encode("utf-8")


def _tree_files(directory: Path) -> dict[str, bytes]:
    if not directory.is_dir():
        return {}
    files: dict[str, bytes] = {}
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        files[path.relative_to(directory).as_posix()] = path.read_bytes()
    return files


def expected_files(root: Path) -> dict[str, bytes]:
    """Return the complete generated Codex tree as repo-relative bytes."""
    name = _plugin_name(root)
    plugin = _load_json(root / ".claude-plugin" / "plugin.json")
    marketplace = _load_json(root / ".claude-plugin" / "marketplace.json")
    plugin_entries = marketplace.get("plugins", [])
    if not isinstance(plugin_entries, list):
        raise SystemExit("`.claude-plugin/marketplace.json` plugins must be a list")

    description = ""
    for entry in plugin_entries:
        if isinstance(entry, dict) and entry.get("name") == name:
            value = entry.get("description", "")
            description = value if isinstance(value, str) else ""
            break

    codex_marketplace = {
        "name": marketplace.get("name", name),
        "owner": marketplace.get("owner", {}),
        "description": marketplace.get("description", ""),
        "plugins": [
            {
                "name": name,
                "source": {"source": "local", "path": f"./plugins/{name}"},
                "description": description,
            }
        ],
    }

    files = {
        f"codex/plugins/{name}/.codex-plugin/plugin.json": _json_bytes(plugin),
        "codex/.agents/plugins/marketplace.json": _json_bytes(codex_marketplace),
    }
    for rel, data in _tree_files(root / "skills").items():
        files[f"codex/plugins/{name}/skills/{rel}"] = data
    for rel, data in _tree_files(root / "agents").items():
        files[f"codex/plugins/{name}/agents/{rel}"] = data
    return files


def _actual_files(root: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for rel, data in _tree_files(root / "codex").items():
        files[f"codex/{rel}"] = data
    return files


def check(root: Path) -> list[str]:
    """Return generated-layout drift descriptions; empty means exact."""
    expected = expected_files(root)
    actual = _actual_files(root)
    errors: list[str] = []
    for path in sorted(set(expected) - set(actual)):
        errors.append(f"missing generated Codex file: {path}")
    for path in sorted(set(actual) - set(expected)):
        errors.append(f"unexpected generated Codex file: {path}")
    for path in sorted(set(expected) & set(actual)):
        if expected[path] != actual[path]:
            errors.append(f"stale generated Codex file: {path}")
    return errors


def build(root: Path) -> Path:
    """Replace the generated Codex tree with its canonical representation."""
    codex_dir = root / "codex"
    if codex_dir.exists():
        shutil.rmtree(codex_dir)
    for rel, data in expected_files(root).items():
        destination = root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    return root / "codex" / "plugins" / _plugin_name(root)


def _parse_args() -> tuple[bool, Path]:
    args = sys.argv[1:]
    check_only = "--check" in args
    positional = [arg for arg in args if arg != "--check"]
    if len(positional) > 1:
        raise SystemExit("usage: build_host_layouts.py [--check] [/path/repo]")
    return check_only, Path(positional[0]) if positional else Path.cwd()


def main() -> int:
    check_only, root = _parse_args()
    if check_only:
        errors = check(root)
        if errors:
            print("\n".join(errors))
            print("\nCodex layout is stale. Run: python scripts/build_host_layouts.py")
            return 1
        print("Codex host layout matches canonical plugin sources")
        return 0

    plugin_dir = build(root)
    marketplace_path = root / "codex" / ".agents" / "plugins" / "marketplace.json"
    print(f"built Codex host layout at {plugin_dir.relative_to(root)}")
    print(f"built Codex marketplace catalog at {marketplace_path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
