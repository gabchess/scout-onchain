"""Build or verify Scout's deterministic, self-contained release archive.

The archive is a portable repository tree. It includes the plugin manifests,
skills, Codex skill layout, Python/MCP runtime, fixtures, docs, tests, and local
verification scripts. Build history is removed from the manifest stored inside
the ZIP so identical source content produces identical bytes.

Usage:
    python scripts/build_release_zip.py
    python scripts/build_release_zip.py --check
    python scripts/build_release_zip.py --check /path/to/repo
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
SUMS_FILENAME = "SHA256SUMS.txt"
EXCLUDED_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".remember",
    ".ruff_cache",
    ".scout",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "tracking",
}
REQUIRED_PATHS = (
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".mcp.json",
    "codex/.agents/plugins/marketplace.json",
    "codex/plugins/scout-portfolio/.codex-plugin/plugin.json",
    "codex/plugins/scout-portfolio/skills/portfolio-intelligence/SKILL.md",
    "skills/portfolio-intelligence/SKILL.md",
    "src/scout_portfolio_manager/mcp_server.py",
    "fixtures/portfolio.json",
    "fixtures/price_history.json",
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "START-HERE.md",
    "SECURITY.md",
    "DATA-AND-PRIVACY.md",
    "HOST-MATRIX.md",
    "LICENSE.md",
    SUMS_FILENAME,
)
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _read_version(root: Path) -> str:
    manifest = tomllib.loads((root / "pyproject.toml").read_text())
    version = manifest.get("project", {}).get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("pyproject.toml is missing project.version")
    return version


def _is_excluded(parts: tuple[str, ...]) -> bool:
    return (
        not parts
        or any(part in EXCLUDED_DIR_NAMES for part in parts)
        or any(part.endswith(".egg-info") for part in parts)
        or parts[-1] == ".DS_Store"
    )


def _candidate_paths(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return sorted({path for path in result.stdout.decode().split("\0") if path})
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not _is_excluded(path.relative_to(root).parts)
    )


def collect_release_files(root: Path) -> list[tuple[Path, str]]:
    """Return every file in the portable release tree."""
    root = root.resolve()
    files: list[tuple[Path, str]] = []
    for relative in _candidate_paths(root):
        parts = Path(relative).parts
        if _is_excluded(parts) or relative == SUMS_FILENAME:
            continue
        source = root / relative
        if source.is_symlink():
            raise ValueError(f"release input cannot be a symbolic link: {relative}")
        if source.is_file():
            files.append((source, relative))
    return files


def _canonical_release_manifest_bytes(path: Path) -> bytes:
    manifest = _read_json(path)
    manifest.pop("release_artifacts", None)
    return (json.dumps(manifest, indent=2) + "\n").encode()


def _stage(root: Path, staging_root: Path) -> None:
    for source, relative in collect_release_files(root):
        destination = staging_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if relative == "RELEASE-MANIFEST.json":
            destination.write_bytes(_canonical_release_manifest_bytes(source))
        else:
            shutil.copy2(source, destination)
    _write_tree_sums(staging_root)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_sum_lines(root: Path) -> list[str]:
    lines: list[str] = []
    for path in sorted(root.rglob("*")):
        relative_path = path.relative_to(root)
        if path.is_file() and path.name != SUMS_FILENAME and not _is_excluded(relative_path.parts):
            relative = relative_path.as_posix()
            lines.append(f"{_sha256(path)}  {relative}")
    return lines


def _write_tree_sums(root: Path) -> None:
    (root / SUMS_FILENAME).write_text("\n".join(_tree_sum_lines(root)) + "\n")


def _verify_tree_sums(root: Path) -> list[str]:
    path = root / SUMS_FILENAME
    if not path.is_file():
        return [f"archive is missing {SUMS_FILENAME}"]
    expected = _tree_sum_lines(root)
    actual = path.read_text().splitlines()
    return [] if actual == expected else [f"archive-local {SUMS_FILENAME} does not match"]


def _run_gate(command: list[str], *, cwd: Path, label: str) -> list[str]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        return []
    detail = (result.stdout + result.stderr).strip()
    return [f"{label} failed: {detail}"]


def _version_errors(root: Path) -> list[str]:
    expected = _read_version(root)
    values: dict[str, object] = {
        ".claude-plugin/plugin.json": _read_json(root / ".claude-plugin/plugin.json").get(
            "version"
        ),
        "codex plugin.json": _read_json(
            root / "codex/plugins/scout-portfolio/.codex-plugin/plugin.json"
        ).get("version"),
        "LOADOUT-MANIFEST.json": _read_json(root / "LOADOUT-MANIFEST.json").get("version"),
        "RELEASE-MANIFEST.json": _read_json(root / "RELEASE-MANIFEST.json").get("version"),
    }
    return [
        f"version drift: {name} has {value!r}; expected {expected!r}"
        for name, value in values.items()
        if value != expected
    ]


def _required_path_errors(root: Path) -> list[str]:
    return [
        f"archive is missing required path: {path}"
        for path in REQUIRED_PATHS
        if not (root / path).is_file()
    ]


def _local_link_errors(root: Path) -> list[str]:
    errors: list[str] = []
    for markdown in sorted(root.rglob("*.md")):
        for raw_target in MARKDOWN_LINK_RE.findall(markdown.read_text(errors="replace")):
            target = raw_target.strip().strip("<>").split(maxsplit=1)[0]
            if not target or target.startswith("#"):
                continue
            parsed = urlparse(target)
            if parsed.scheme or target.startswith("//"):
                continue
            path_text = unquote(target.split("#", 1)[0])
            if not path_text:
                continue
            if path_text.startswith("/"):
                errors.append(f"absolute local link in {markdown.relative_to(root)}: {target}")
                continue
            destination = (markdown.parent / path_text).resolve()
            try:
                destination.relative_to(root.resolve())
            except ValueError:
                errors.append(f"link escapes archive in {markdown.relative_to(root)}: {target}")
                continue
            if not destination.exists():
                errors.append(f"broken local link in {markdown.relative_to(root)}: {target}")
    return errors


def _smoke_errors(root: Path) -> list[str]:
    code = (
        "from scout_portfolio_manager.host import ReadOnlyHost; "
        "r=ReadOnlyHost('fixtures/portfolio.json').get_portfolio_snapshot(); "
        "assert r['status']=='ok'"
    )
    env = os.environ.copy()
    for name in (
        "ZERION_API_KEY",
        "ZERION_X402_PRIVATE_KEY",
        "ZERION_WALLET_ADDRESS",
        "ZPM_FIXTURE_PATH",
    ):
        env.pop(name, None)
    env["PYTHONPATH"] = str(root / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return []
    return [f"extracted fixture smoke failed: {(result.stdout + result.stderr).strip()}"]


def _staged_tree_errors(root: Path) -> list[str]:
    errors = _required_path_errors(root)
    errors.extend(_version_errors(root))
    errors.extend(_verify_tree_sums(root))
    errors.extend(_local_link_errors(root))
    errors.extend(
        _run_gate(
            [sys.executable, "scripts/security_scan.py", "."],
            cwd=root,
            label="archive secret scan",
        )
    )
    errors.extend(
        _run_gate(
            [sys.executable, "scripts/check_plugin_manifest.py", "."],
            cwd=root,
            label="archive plugin contract",
        )
    )
    errors.extend(_smoke_errors(root))
    return errors


def _source_preflight_errors(root: Path) -> list[str]:
    errors = _version_errors(root)
    errors.extend(
        _run_gate(
            [sys.executable, "scripts/build_host_layouts.py", "--check"],
            cwd=root,
            label="generated Codex layout",
        )
    )
    errors.extend(
        _run_gate(
            [sys.executable, "scripts/write_checksums.py", "--check"],
            cwd=root,
            label="source checksum ledger",
        )
    )
    errors.extend(
        _run_gate(
            [sys.executable, "scripts/gen_doc_manifest.py", "--check"],
            cwd=root,
            label="documentation manifest",
        )
    )
    return errors


def _write_deterministic_zip(staging_root: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging_root.rglob("*")):
            relative_path = path.relative_to(staging_root)
            if not path.is_file() or _is_excluded(relative_path.parts):
                continue
            relative = relative_path.as_posix()
            info = zipfile.ZipInfo(relative, date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def build(root: Path, destination: Path | None = None) -> Path:
    """Build one verified archive without changing source manifests."""
    root = root.resolve()
    preflight = _source_preflight_errors(root)
    if preflight:
        raise ValueError("\n".join(preflight))
    version = _read_version(root)
    zip_path = destination or root / "dist" / f"scout-portfolio-{version}.zip"
    with tempfile.TemporaryDirectory() as temporary:
        staging_root = Path(temporary)
        _stage(root, staging_root)
        errors = _staged_tree_errors(staging_root)
        if errors:
            raise ValueError("\n".join(errors))
        _write_deterministic_zip(staging_root, zip_path)
    return zip_path


def check(root: Path) -> list[str]:
    """Verify archive composition and determinism without changing the repo."""
    try:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            first = build(root, temp / "first.zip")
            second = build(root, temp / "second.zip")
            if _sha256(first) != _sha256(second):
                return ["two builds from the same source produced different ZIP bytes"]
            extracted = temp / "extracted"
            with zipfile.ZipFile(first) as archive:
                archive.extractall(extracted)
            return _staged_tree_errors(extracted)
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        return [str(exc)]


def _update_release_manifest(root: Path, zip_path: Path, digest: str) -> None:
    manifest_path = root / "RELEASE-MANIFEST.json"
    manifest = _read_json(manifest_path)
    relative = zip_path.relative_to(root).as_posix()
    artifacts = manifest.setdefault("release_artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("RELEASE-MANIFEST.json release_artifacts must be a list")
    artifacts[:] = [
        item for item in artifacts if not isinstance(item, dict) or item.get("path") != relative
    ]
    artifacts.append(
        {
            "path": relative,
            "sha256": digest,
            "version": _read_version(root),
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


def _refresh_source_checksums(root: Path) -> None:
    result = subprocess.run(
        [sys.executable, "scripts/write_checksums.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError((result.stdout + result.stderr).strip())


def _parse_args() -> tuple[bool, Path]:
    args = sys.argv[1:]
    check_only = "--check" in args
    positional = [arg for arg in args if arg != "--check"]
    if len(positional) > 1:
        raise SystemExit("usage: build_release_zip.py [--check] [/path/to/repo]")
    return check_only, Path(positional[0]) if positional else Path.cwd()


def main() -> int:
    check_only, root = _parse_args()
    if check_only:
        errors = check(root)
        if errors:
            print("\n".join(errors))
            return 1
        print("release archive contract passed")
        return 0

    try:
        zip_path = build(root)
        digest = _sha256(zip_path)
        _update_release_manifest(root.resolve(), zip_path.resolve(), digest)
        _refresh_source_checksums(root.resolve())
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        print(exc)
        return 1
    print(f"built {zip_path.resolve().relative_to(root.resolve())}")
    print(f"sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
