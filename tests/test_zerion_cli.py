"""Real bounded subprocess checks; fake CLI has no network or wallet access."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from scout_portfolio_manager.zerion_cli import (
    ZerionCliProvider,
    bounded_process,
    preparation_from_env,
)
from scout_portfolio_manager.zerion_prepare import PreparationIntent


def test_disabled_ignores_existing_wallet_credentials():
    service = preparation_from_env(
        {"ZPM_ZERION_PREPARE_API_KEY": "test", "ZERION_X402_PRIVATE_KEY": "never-used"}
    )
    assert service.get_status("id")["status"] == "disabled"


@pytest.mark.parametrize(
    "env",
    [
        {"ZPM_ZERION_PREPARE_ENABLED": "true"},
        {"ZPM_ZERION_PREPARE_ENABLED": "1"},
        {"ZPM_ZERION_PREPARE_ENABLED": "1", "ZPM_ZERION_PREPARE_STORE": "relative"},
    ],
)
def test_invalid_operator_config_is_an_error(env):
    with pytest.raises(ValueError):
        preparation_from_env(env)


def test_subprocess_does_not_interpret_shell_syntax():
    result = bounded_process(
        [sys.executable, "-c", "import sys; print(sys.argv[1])", "$(whoami); rm -rf /"], {}
    )
    assert result.strip() == "$(whoami); rm -rf /"


@pytest.mark.parametrize(
    "code,exception",
    [
        ("import time; time.sleep(2)", TimeoutError),
        ('print("x"*1100000)', ValueError),
        ('import sys; sys.stderr.write("x"*1100000)', ValueError),
        ("raise SystemExit(1)", ValueError),
    ],
)
def test_bounded_process_failures(code, exception):
    with pytest.raises(exception):
        bounded_process([sys.executable, "-c", code], {}, timeout=0.5)


def cli_fixture(root: Path, version="1.9.1") -> Path:
    (root / "cli").mkdir()
    (root / "package.json").write_text(json.dumps({"name": "zerion-cli", "version": version}))
    path = root / "cli/zerion.js"
    path.write_text(
        "#!" + sys.executable + "\nimport json,os,sys\n"
        'print(json.dumps({"argv":sys.argv[1:],"env":sorted(os.environ)}))\n'
    )
    path.chmod(0o700)
    return path


def test_real_subprocess_argv_and_credential_minimization(tmp_path):
    cli = cli_fixture(tmp_path)
    provider = ZerionCliProvider(
        cli,
        {
            "PATH": os.defpath,
            "ZPM_ZERION_PREPARE_API_KEY": "fixture-test",
            "ZERION_AGENT_TOKEN": "must-not-pass",
            "NODE_OPTIONS": "bad",
            "ZERION_UNSAFE_POLICY_PATHS": "1",
        },
    )
    request = PreparationIntent(
        action="swap",
        chain="base",
        source_wallet="0x" + "1" * 40,
        asset="0x" + "2" * 40,
        amount="1",
        target_asset="native",
    )
    result = provider.prepare(request)
    assert result["argv"] == request.cli_args()
    assert "--prepare" in result["argv"] and "--review" in result["argv"]
    assert "ZERION_AGENT_TOKEN" not in result["env"]
    assert "NODE_OPTIONS" not in result["env"]
    assert "ZERION_UNSAFE_POLICY_PATHS" not in result["env"]


def test_unknown_cli_version_rejected_before_launch(tmp_path):
    cli = cli_fixture(tmp_path, version="2.0.0")
    with pytest.raises(ValueError, match="version"):
        ZerionCliProvider(cli, {"ZPM_ZERION_PREPARE_API_KEY": "test"})
