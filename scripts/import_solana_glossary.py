#!/usr/bin/env python3
"""Build Scout's pinned Solana glossary from an explicit local checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

REPOSITORY_URL = "https://github.com/solanabr/solana-glossary"
TERMS_DIR = Path("packages/glossary/data/terms")
LICENSE_FILE = Path("packages/glossary/LICENSE")
STATUS = "community_reference_unverified"
CANONICAL_REPOSITORY = "github.com/solanabr/solana-glossary"


def _git(checkout: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(checkout), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise ValueError(f"cannot read source Git checkout: {checkout}") from error
    return result.stdout


def _git_sha(checkout: Path) -> str:
    sha = _git(checkout, "rev-parse", "HEAD").strip()
    if len(sha) != 40 or any(character not in "0123456789abcdef" for character in sha):
        raise ValueError("source checkout did not return a full lowercase Git SHA")
    return sha


def _canonical_origin(checkout: Path) -> None:
    origin = _git(checkout, "config", "--get", "remote.origin.url").strip()
    normalized = origin.removesuffix(".git")
    if normalized.startswith("git@github.com:"):
        normalized = "github.com/" + normalized.removeprefix("git@github.com:")
    elif normalized.startswith("ssh://git@github.com/"):
        normalized = "github.com/" + normalized.removeprefix("ssh://git@github.com/")
    else:
        normalized = normalized.removeprefix("https://").removeprefix("http://")
    if normalized.lower() != CANONICAL_REPOSITORY:
        raise ValueError(f"source origin is not canonical {REPOSITORY_URL}: {origin}")


def _committed_text(checkout: Path, source_sha: str, relative_path: str) -> str:
    return _git(checkout, "show", f"{source_sha}:{relative_path}")


def _source_digest(files: list[tuple[str, bytes]]) -> str:
    digest = hashlib.sha256()
    for relative_path, content in files:
        relative = relative_path.encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def build_glossary(checkout: Path) -> dict[str, Any]:
    checkout = checkout.resolve()
    if not checkout.is_dir() or not (checkout / ".git").exists():
        raise ValueError(f"source checkout is not a Git working tree: {checkout}")

    _canonical_origin(checkout)
    source_sha = _git_sha(checkout)
    listed = _git(
        checkout,
        "ls-tree",
        "-r",
        "--name-only",
        source_sha,
        "--",
        TERMS_DIR.as_posix(),
    ).splitlines()
    source_files = sorted(path for path in listed if path.endswith(".json"))
    if not source_files:
        raise ValueError(f"no committed glossary JSON files found in: {TERMS_DIR}")

    committed_sources = [
        (path, _committed_text(checkout, source_sha, path).encode("utf-8")) for path in source_files
    ]

    imported: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for relative_source, content in committed_sources:
        raw = json.loads(content.decode("utf-8"))
        if not isinstance(raw, list):
            raise ValueError(f"expected a JSON array in {relative_source}")
        for index, record in enumerate(raw):
            if not isinstance(record, dict):
                raise ValueError(f"expected an object at {relative_source}[{index}]")
            required = ("id", "term", "definition", "category")
            malformed_required = any(
                not isinstance(record.get(key), str) or not record[key].strip() for key in required
            )
            if malformed_required:
                raise ValueError(f"malformed required field at {relative_source}[{index}]")
            term_id = record["id"]
            if term_id in seen_ids:
                raise ValueError(f"duplicate glossary id: {term_id}")
            seen_ids.add(term_id)
            aliases = record.get("aliases", [])
            related = record.get("related", [])
            aliases_are_strings = isinstance(aliases, list) and all(
                isinstance(value, str) for value in aliases
            )
            if not aliases_are_strings:
                raise ValueError(f"malformed aliases for {term_id}")
            related_are_strings = isinstance(related, list) and all(
                isinstance(value, str) for value in related
            )
            if not related_are_strings:
                raise ValueError(f"malformed related list for {term_id}")
            imported.append(
                {
                    "id": term_id,
                    "term": record["term"],
                    "aliases": aliases,
                    "definition": f"[{STATUS}] {record['definition']}",
                    "category": record["category"],
                    "related": related,
                    "source_url": (f"{REPOSITORY_URL}/blob/{source_sha}/{relative_source}"),
                    "source_sha": source_sha,
                    "source_file": relative_source,
                }
            )

    imported.sort(key=lambda item: (item["id"], item["source_file"]))
    license_text = _committed_text(checkout, source_sha, LICENSE_FILE.as_posix())
    if "MIT License" not in license_text or "Superteam Brazil" not in license_text:
        raise ValueError("source license is not the expected Superteam Brazil MIT license")
    return {
        "version": 1,
        "provenance": {
            "name": "Solana Glossary",
            "publisher": "Superteam Brazil",
            "repository_url": REPOSITORY_URL,
            "source_sha": source_sha,
            "source_files": source_files,
            "source_content_sha256": _source_digest(committed_sources),
            "license": "MIT",
            "license_file": LICENSE_FILE.as_posix(),
            "license_text": license_text,
            "definition_status": STATUS,
            "verification_policy": (
                "Community reference only. Verify numerical, operational, version-specific, "
                "security-sensitive, and time-sensitive claims against current primary sources."
            ),
            "malformed_exclusions": [],
            "term_count": len(imported),
        },
        "terms": imported,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_checkout", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = build_glossary(args.source_checkout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
