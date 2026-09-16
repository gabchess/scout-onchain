"""Validate the package's local plugin/entry-point contract without network access."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

EXPECTED_ENTRY_POINT = "scout_portfolio_manager.mcp_server:main"
EXPECTED_SCRIPTS = ("zpm-mcp", "scout-portfolio-manager")
README_MARKERS = (
    "START-HERE.md",
    "zpm-mcp",
    "docs/X402.md",
    "approval_state=required",
)


def check(root: Path) -> list[str]:
    """Return actionable violations in the package manifest and README."""
    errors: list[str] = []
    pyproject_path = root / "pyproject.toml"
    readme_path = root / "README.md"
    try:
        manifest = tomllib.loads(pyproject_path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"cannot read {pyproject_path}: {exc}"]
    try:
        readme = readme_path.read_text()
    except OSError as exc:
        return [f"cannot read {readme_path}: {exc}"]

    scripts = manifest.get("project", {}).get("scripts", {})
    for name in EXPECTED_SCRIPTS:
        if scripts.get(name) != EXPECTED_ENTRY_POINT:
            errors.append(f"project.scripts.{name} must be {EXPECTED_ENTRY_POINT!r}")
    dependencies = manifest.get("project", {}).get("dependencies", [])
    if not any(str(dep).replace(" ", "").startswith("mcp>=") for dep in dependencies):
        errors.append("project.dependencies must include the mcp SDK")
    if "[project.optional-dependencies]" not in pyproject_path.read_text():
        errors.append("pyproject.toml must declare optional dependencies")
    for marker in README_MARKERS:
        if marker not in readme:
            errors.append(f"README.md is missing plugin documentation marker: {marker}")
    return errors


def main() -> int:
    errors = check(Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd())
    if errors:
        print("\n".join(errors))
        return 1
    print("plugin manifest and README checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
