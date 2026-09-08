"""Generate and verify documentation-manifest.json for the release docs set.

Same deterministic shape as `scripts/write_checksums.py`: sorted paths, forward
slashes, lowercase sha256 hex. Covers every markdown doc at the repo root and
under `docs/` (recursively), minus the manifest itself (JSON, not markdown).
The product version is read from `pyproject.toml` so the manifest cannot drift
from the release version; `claim_boundary` quotes CLAIMS.md's own language.

Usage:
    python scripts/gen_doc_manifest.py            # write/refresh documentation-manifest.json
    python scripts/gen_doc_manifest.py --check     # verify, exit 1 on drift
"""

from __future__ import annotations

import hashlib
import json
import sys
import tomllib
from pathlib import Path

MANIFEST_FILENAME = "documentation-manifest.json"
FORMAT = "cd-documentation-manifest/v1"
CLAIM_BOUNDARY = (
    "Fixture is the default; Zerion observes one wallet; x402 can sign and pay "
    "data fees; host and MCP have no trade execution tool."
)


def _read_version(root: Path) -> str:
    manifest = tomllib.loads((root / "pyproject.toml").read_text())
    version = manifest.get("project", {}).get("version")
    if not version:
        raise SystemExit("pyproject.toml is missing project.version")
    return str(version)


def _doc_paths(root: Path) -> list[str]:
    """Every markdown doc at the repo root and under docs/, sorted."""
    paths = [p.name for p in root.glob("*.md") if p.is_file()]
    docs = root / "docs"
    if docs.is_dir():
        paths += [
            p.relative_to(root).as_posix() for p in docs.rglob("*.md") if p.is_file()
        ]
    return sorted(set(paths))


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_manifest(root: Path) -> str:
    payload = {
        "format": FORMAT,
        "product": "scout-portfolio-manager",
        "version": _read_version(root),
        "claim_boundary": CLAIM_BOUNDARY,
        "files": [
            {"path": rel, "sha256": _sha256_of(root / rel)} for rel in _doc_paths(root)
        ],
    }
    return json.dumps(payload, indent=2) + "\n"


def check(root: Path) -> list[str]:
    """Return a list of drift descriptions; empty means no drift."""
    manifest_path = root / MANIFEST_FILENAME
    if not manifest_path.exists():
        return [f"{MANIFEST_FILENAME} does not exist; run without --check to create it"]
    expected = compute_manifest(root)
    if manifest_path.read_text() == expected:
        return []
    # Report per-file drift so a stale hash names the doc that moved.
    errors = ["documentation-manifest.json is stale"]
    try:
        actual_files = {
            f["path"]: f["sha256"] for f in json.loads(manifest_path.read_text())["files"]
        }
    except (json.JSONDecodeError, KeyError, TypeError):
        return errors
    expected_files = {
        f["path"]: f["sha256"] for f in json.loads(expected)["files"]
    }
    for path in sorted(set(actual_files) - set(expected_files)):
        errors.append(f"entry for removed or renamed doc: {path}")
    for path in sorted(set(expected_files) - set(actual_files)):
        errors.append(f"missing entry: {path}")
    for path in sorted(set(actual_files) & set(expected_files)):
        if actual_files[path] != expected_files[path]:
            errors.append(f"drifted sha256: {path}")
    return errors


def main() -> int:
    root = Path.cwd()
    if "--check" in sys.argv[1:]:
        errors = check(root)
        if errors:
            print("\n".join(errors))
            print(f"\n{MANIFEST_FILENAME} is stale. Run: python scripts/gen_doc_manifest.py")
            return 1
        print(f"{MANIFEST_FILENAME} matches the tree")
        return 0

    manifest_path = root / MANIFEST_FILENAME
    manifest_path.write_text(compute_manifest(root))
    count = len(json.loads(manifest_path.read_text())["files"])
    print(f"wrote {manifest_path} ({count} docs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
