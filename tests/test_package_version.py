"""Guard against the package version drifting from pyproject.toml."""

import tomllib
from pathlib import Path

import scout_portfolio_manager

ROOT = Path(__file__).resolve().parents[1]


def test_package_version_matches_pyproject():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    expected = pyproject["project"]["version"]
    assert scout_portfolio_manager.__version__ == expected


def test_console_script_alias_shares_the_mcp_entry_point():
    from importlib.metadata import entry_points

    scripts = {ep.name: ep.value for ep in entry_points(group="console_scripts")}
    assert scripts["scout-portfolio-manager"] == "scout_portfolio_manager.mcp_server:main"
    assert scripts["zpm-mcp"] == scripts["scout-portfolio-manager"]
