from pathlib import Path

from scripts.check_plugin_manifest import check as check_plugin_manifest
from scripts.security_scan import scan

ROOT = Path(__file__).parents[1]


def test_repository_has_no_credential_shaped_secrets():
    assert scan(ROOT) == []


def test_secret_scan_detects_private_key_in_fixture_tree(tmp_path):
    (tmp_path / "example.txt").write_text("token = '0x" + "a" * 64 + "'\n")
    assert scan(tmp_path) == [str(tmp_path / "example.txt") + ":1"]


def test_secret_scan_detects_vendor_prefixed_tokens(tmp_path):
    cases = {
        "github-pat.txt": "ghp_" + "a" * 36,
        "github-server.txt": "ghs_" + "b" * 36,
        "openai.txt": "sk-" + "c" * 25,
        "stripe.txt": "sk_live_" + "d" * 20,
        "slack.txt": "xoxb-" + "e" * 15,
        "google.txt": "AIza" + "f" * 35,
        "jwt.txt": "eyJ" + "a" * 10 + "." + "b" * 10 + "." + "c" * 10,
    }
    for name, token in cases.items():
        (tmp_path / name).write_text(f"token = {token}\n")
    findings = scan(tmp_path)
    assert len(findings) == len(cases)


def test_secret_scan_detects_bare_bip39_mnemonic_on_its_own_line(tmp_path):
    words = " ".join(["abandon"] * 11 + ["about"])
    (tmp_path / "leak.txt").write_text(words + "\n")
    assert scan(tmp_path) == [str(tmp_path / "leak.txt") + ":1"]


def test_secret_scan_does_not_flag_ordinary_prose(tmp_path):
    prose = (
        "the launcher fix keeps the mcp server working when no virtual "
        "environment is active for the caller at all\n"
    )
    (tmp_path / "prose.md").write_text(prose)
    assert scan(tmp_path) == []


def test_secret_scan_covers_tests_directory(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "fixture_with_secret.py").write_text("token = 'sk-" + "a" * 25 + "'\n")
    assert scan(tmp_path) == [str(tests_dir / "fixture_with_secret.py") + ":1"]


def test_plugin_manifest_and_readme_contract_is_complete():
    assert check_plugin_manifest(ROOT) == []


def test_plugin_manifest_requires_both_console_scripts(tmp_path):
    pyproject = (ROOT / "pyproject.toml").read_text()
    (tmp_path / "README.md").write_text((ROOT / "README.md").read_text())
    (tmp_path / "pyproject.toml").write_text(
        pyproject.replace('scout-portfolio-manager = "scout_portfolio_manager.mcp_server:main"', "")
    )
    assert check_plugin_manifest(tmp_path) == [
        "project.scripts.scout-portfolio-manager must be "
        "'scout_portfolio_manager.mcp_server:main'"
    ]


def test_plugin_manifest_requires_mcp_core_dependency(tmp_path):
    pyproject = (ROOT / "pyproject.toml").read_text()
    (tmp_path / "README.md").write_text((ROOT / "README.md").read_text())
    (tmp_path / "pyproject.toml").write_text(pyproject.replace(', "mcp>=1.2,<2"]', "]"))
    assert check_plugin_manifest(tmp_path) == ["project.dependencies must include the mcp SDK"]
