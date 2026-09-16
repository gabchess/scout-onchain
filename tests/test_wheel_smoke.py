import zipfile

from scripts.wheel_smoke import REQUIRED_WHEEL_DATA, check_wheel


def test_check_wheel_reports_missing_package_data(tmp_path):
    wheel = tmp_path / "scout.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("scout_portfolio_manager/__init__.py", "")
    assert check_wheel(wheel) == list(REQUIRED_WHEEL_DATA)


def test_check_wheel_accepts_complete_package_data(tmp_path):
    wheel = tmp_path / "scout.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for path in REQUIRED_WHEEL_DATA:
            archive.writestr(path, "{}")
    assert check_wheel(wheel) == []
