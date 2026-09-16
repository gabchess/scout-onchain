import json
import logging
import os
from pathlib import Path

import pytest

from scout_portfolio_manager.alerts import AlertStore, default_alerts_path
from scout_portfolio_manager.host import ReadOnlyHost

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "portfolio.json"


def test_env_override_wins(tmp_path):
    target = tmp_path / "custom" / "alerts.json"
    assert default_alerts_path({"ZPM_ALERTS_PATH": str(target)}) == target


def test_empty_env_override_falls_back_to_home():
    assert default_alerts_path({"ZPM_ALERTS_PATH": "  "}) == Path.home() / ".scout" / "alerts.json"


def test_home_default_when_unset():
    assert default_alerts_path({}) == Path.home() / ".scout" / "alerts.json"


def test_host_default_writes_under_home_not_cwd(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    ReadOnlyHost(FIXTURE).set_alert("ETH", "rsi_below", 30.0)
    assert (Path.home() / ".scout" / "alerts.json").exists()
    assert not (cwd / ".scout").exists()


def test_host_honors_env_override(tmp_path, monkeypatch):
    target = tmp_path / "env-alerts.json"
    monkeypatch.setenv("ZPM_ALERTS_PATH", str(target))
    ReadOnlyHost(FIXTURE).set_alert("ETH", "rsi_below", 30.0)
    assert len(json.loads(target.read_text())) == 1


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_read_only_cwd_does_not_break_set_alert(tmp_path, monkeypatch):
    cwd = tmp_path / "readonly"
    cwd.mkdir()
    cwd.chmod(0o555)
    monkeypatch.chdir(cwd)
    try:
        result = ReadOnlyHost(FIXTURE).set_alert("ETH", "rsi_below", 30.0)
    finally:
        cwd.chmod(0o755)
    assert result["status"] == "ok"
    assert result["rule_count"] == 1


def _legacy_file(cwd: Path) -> Path:
    legacy = cwd / ".scout" / "alerts.json"
    legacy.parent.mkdir(parents=True)
    store = AlertStore(legacy)
    store.add(asset="btc", kind="rsi_below", threshold=25.0)
    return legacy


def test_legacy_cwd_file_is_imported_once_with_warning(tmp_path, monkeypatch, caplog):
    cwd = tmp_path / "project"
    cwd.mkdir()
    legacy = _legacy_file(cwd)
    monkeypatch.chdir(cwd)

    with caplog.at_level(logging.WARNING):
        rules = ReadOnlyHost(FIXTURE).check_alerts()
    assert "legacy" in caplog.text and "ZPM_ALERTS_PATH" in caplog.text
    assert rules["status"] == "ok"
    home_file = Path.home() / ".scout" / "alerts.json"
    assert [r["asset"] for r in json.loads(home_file.read_text())] == ["BTC"]
    assert legacy.exists()

    caplog.clear()
    legacy.write_text("[]")
    with caplog.at_level(logging.WARNING):
        store = AlertStore(home_file, legacy_path=legacy)
        assert [r.asset for r in store.list()] == ["BTC"]
        assert [r.asset for r in store.list()] == ["BTC"]
    assert "copied" not in caplog.text
    assert caplog.text.count("ignoring legacy") == 1


def test_legacy_file_ignored_when_env_override_set(tmp_path, monkeypatch):
    cwd = tmp_path / "project"
    cwd.mkdir()
    _legacy_file(cwd)
    monkeypatch.chdir(cwd)
    target = tmp_path / "explicit.json"
    monkeypatch.setenv("ZPM_ALERTS_PATH", str(target))
    host = ReadOnlyHost(FIXTURE)
    assert host._alert_store.list() == []


def test_alert_store_directory_and_file_are_private(tmp_path):
    target = tmp_path / "fresh" / "alerts.json"
    AlertStore(target).add(asset="eth", kind="rsi_below", threshold=30.0)
    assert target.parent.stat().st_mode & 0o777 == 0o700
    assert target.stat().st_mode & 0o777 == 0o600


def test_existing_world_readable_alert_file_is_tightened(tmp_path):
    target = tmp_path / "alerts.json"
    target.write_text("[]")
    target.chmod(0o644)
    AlertStore(target).add(asset="eth", kind="rsi_below", threshold=30.0)
    assert target.stat().st_mode & 0o777 == 0o600
