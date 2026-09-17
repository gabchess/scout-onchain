"""Keep internal agent-process files and names out of the public tree."""

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
THIS_FILE = Path(__file__).relative_to(ROOT).as_posix()
# Ignore files list the internal paths on purpose, to keep them out.
SKIPPED = {THIS_FILE, "uv.lock", ".gitignore", ".dockerignore"}
SKIPPED_PREFIXES = ("src/scout_portfolio_manager/data/",)
INTERNAL_PATH = re.compile(r"superpowers|^docs/(plans|specs)/")
INTERNAL_TEXT = re.compile(
    r"\b(harrier|kestrel|hyperbots)\b|(\.|docs/)superpowers\b", re.IGNORECASE
)


def _tracked_files() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=False
        )
    except FileNotFoundError:
        pytest.skip("git is not installed")
    if result.returncode != 0:
        pytest.skip("not a git checkout")
    return [p for p in result.stdout.decode("utf-8").split("\0") if p]


def test_no_internal_planning_paths_are_tracked():
    assert [p for p in _tracked_files() if INTERNAL_PATH.search(p)] == []


def test_tracked_text_files_do_not_name_internal_process():
    findings = []
    for rel in _tracked_files():
        if rel in SKIPPED or rel.startswith(SKIPPED_PREFIXES):
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if INTERNAL_TEXT.search(line):
                findings.append(f"{rel}:{number}")
    assert findings == []
