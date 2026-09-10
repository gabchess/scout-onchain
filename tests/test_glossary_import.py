from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.import_solana_glossary import STATUS, build_glossary

ROOT = Path(__file__).parents[1]
BUILT_GLOSSARY = ROOT / "src/scout_portfolio_manager/data/solana_glossary.json"
CANONICAL_ORIGIN = "https://github.com/solanabr/solana-glossary.git"
LICENSE = """MIT License

Copyright (c) 2026 Superteam Brazil
"""


def _run_git(checkout: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(checkout), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _source_fixture(tmp_path: Path) -> Path:
    checkout = tmp_path / "source"
    terms = checkout / "packages/glossary/data/terms"
    terms.mkdir(parents=True)
    (checkout / "packages/glossary/LICENSE").write_text(LICENSE, encoding="utf-8")
    records = [
        {
            "id": "account",
            "term": "Account",
            "definition": "A record in the ledger.",
            "category": "core-protocol",
            "aliases": ["ledger account"],
            "related": ["program"],
        },
        {
            "id": "program",
            "term": "Program",
            "definition": "Executable code stored on-chain.",
            "category": "programming-model",
        },
    ]
    (terms / "core.json").write_text(json.dumps(records), encoding="utf-8")
    _run_git(checkout, "init", "-q")
    _run_git(checkout, "config", "user.email", "tests@example.invalid")
    _run_git(checkout, "config", "user.name", "Scout Tests")
    _run_git(checkout, "remote", "add", "origin", CANONICAL_ORIGIN)
    _run_git(checkout, "add", ".")
    _run_git(checkout, "commit", "-qm", "fixture")
    return checkout


def test_import_preserves_shape_and_provenance(tmp_path: Path) -> None:
    payload = build_glossary(_source_fixture(tmp_path))

    assert payload["version"] == 1
    assert payload["provenance"]["term_count"] == 2
    assert payload["provenance"]["license"] == "MIT"
    assert "Copyright (c) 2026 Superteam Brazil" in payload["provenance"]["license_text"]
    assert payload["provenance"]["malformed_exclusions"] == []
    assert len(payload["terms"]) == 2
    assert len({term["id"] for term in payload["terms"]}) == 2

    expected_keys = {
        "id",
        "term",
        "aliases",
        "definition",
        "category",
        "related",
        "source_url",
        "source_sha",
        "source_file",
    }
    assert all(set(term) == expected_keys for term in payload["terms"])
    assert all(term["definition"].startswith(f"[{STATUS}] ") for term in payload["terms"])
    assert all(term["source_url"].endswith(term["source_file"]) for term in payload["terms"])
    assert all(not term["source_file"].startswith("/") for term in payload["terms"])


def test_import_is_deterministic(tmp_path: Path) -> None:
    source = _source_fixture(tmp_path)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    script = Path(__file__).parents[1] / "scripts" / "import_solana_glossary.py"

    for output in (first, second):
        subprocess.run(
            [sys.executable, str(script), str(source), str(output)],
            check=True,
            capture_output=True,
            text=True,
        )

    assert first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_text(encoding="utf-8"))["provenance"]["term_count"] == 2


def test_import_ignores_dirty_and_untracked_worktree_files(tmp_path: Path) -> None:
    source = _source_fixture(tmp_path)
    clean = build_glossary(source)
    terms = source / "packages/glossary/data/terms"
    (terms / "core.json").write_text("[]", encoding="utf-8")
    (terms / "untracked.json").write_text(
        json.dumps(
            [
                {
                    "id": "false-pin",
                    "term": "False Pin",
                    "definition": "Must not be imported.",
                    "category": "security",
                }
            ]
        ),
        encoding="utf-8",
    )

    assert build_glossary(source) == clean


@pytest.mark.parametrize(
    "origin",
    [
        "https://github.com/example/solana-glossary.git",
        "git@github.com:example/solana-glossary.git",
    ],
)
def test_import_rejects_fork_origin(tmp_path: Path, origin: str) -> None:
    source = _source_fixture(tmp_path)
    _run_git(source, "remote", "set-url", "origin", origin)

    with pytest.raises(ValueError, match="source origin is not canonical"):
        build_glossary(source)


def test_included_bundle_has_full_offline_provenance() -> None:
    payload = json.loads(BUILT_GLOSSARY.read_text(encoding="utf-8"))

    assert payload["provenance"]["source_sha"] == "a91baa510c4db974dfab86669439c6db39a55daf"
    assert payload["provenance"]["term_count"] == 1059
    assert len(payload["terms"]) == 1059
    assert len({term["id"] for term in payload["terms"]}) == 1059
    assert all(
        term["source_sha"] == payload["provenance"]["source_sha"] for term in payload["terms"]
    )


def test_import_rejects_bad_checkout_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a Git working tree"):
        build_glossary(tmp_path / "missing")
