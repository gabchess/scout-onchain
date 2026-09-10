"""Run fresh fixture-only Codex sessions; keep private rubrics out of model context.

This runner records evidence and never grades its own answers. Use a separate
reviewer to freeze the suite before execution and grade retained responses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def load_prompts(path: Path) -> list[dict[str, str]]:
    suite = json.loads(path.read_text())
    cases = (
        suite
        if isinstance(suite, list)
        else suite.get("cases")
        if isinstance(suite, dict)
        else None
    )
    if not isinstance(cases, list) or not 1 <= len(cases) <= 100:
        raise ValueError("Suite needs 1..100 cases")
    result, seen = [], set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Each case must be an object")
        identifier, prompt = case.get("id"), case.get("prompt")
        if not isinstance(identifier, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", identifier
        ):
            raise ValueError("Case ID must be a safe file component")
        if identifier in seen or not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Duplicate ID or empty prompt")
        seen.add(identifier)
        result.append({"id": identifier, "prompt": prompt})
    return result


def context_for(repo: Path) -> str:
    instructions = (
        "You are Scout, the onchain portfolio manager. Use the attached Scout MCP when useful. "
        "This is a fixture-only evaluation. No live web, shell, file access, payment or execution. "
        "Preserve unknowns and source status.\n"
    )
    for name in (
        "skills/defi-research/SKILL.md",
        "skills/defi-research/reference.md",
        "skills/portfolio-intelligence/SKILL.md",
    ):
        instructions += (repo / name).read_text() + "\n"
    return instructions


def runtime_hash(repo: Path) -> str:
    digest = hashlib.sha256()
    for directory in (repo / "src/scout_portfolio_manager", repo / "skills"):
        for path in sorted(directory.rglob("*")):
            if (
                path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix in (".py", ".md", ".json")
            ):
                digest.update(str(path.relative_to(repo)).encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def preflight_mcp(python: Path, launcher: Path, output: Path) -> None:
    """Prove the configured interpreter can start and call the fixture server."""
    probe = """
import asyncio, json, os, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
    params = StdioServerParameters(command=sys.executable, args=[sys.argv[1]],
        env={"PATH": os.defpath, "PYTHONNOUSERSITE": "1"})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = sorted(t.name for t in (await session.list_tools()).tools)
            assert "get_portfolio_risk" in names and "search_defi_knowledge" in names
            result = await session.call_tool("get_portfolio_risk", {"shock_pct": -30})
            assert not result.isError
            data = json.loads(result.content[0].text)
            assert data["source"]["kind"] == "fixture"
            print(json.dumps({"tools": names, "fixture_call_passed": True}))
asyncio.run(main())
"""
    completed = subprocess.run(
        [str(python), "-c", probe, str(launcher)],
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
        env={"PATH": os.defpath, "PYTHONNOUSERSITE": "1"},
    )
    (output / "mcp-preflight.json").write_text(completed.stdout)


def run(suite: Path, repo: Path, output: Path, python: Path) -> None:
    prompts = load_prompts(suite)
    context = context_for(repo)
    before = runtime_hash(repo)
    output.mkdir(parents=True, exist_ok=False)
    launcher = output / "fixture_mcp.py"
    launcher.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(repo / 'src')!r})\n"
        "from scout_portfolio_manager.host import default_host\n"
        "from scout_portfolio_manager.mcp_server import create_server\n"
        "create_server(default_host()).run(transport='stdio')\n"
    )
    preflight_mcp(python, launcher, output)
    config = {
        "web_search": "disabled",
        "features.shell_tool": False,
        "features.skip_host_skill_discovery": True,
        "features.multi_agent": False,
        "mcp_servers.scout.default_tools_approval_mode": "approve",
        "developer_instructions": context,
        "mcp_servers.scout.command": str(python),
        "mcp_servers.scout.args": [str(launcher)],
    }
    args = [
        "codex",
        "exec",
        "--ignore-user-config",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--json",
        "-C",
        str(output),
    ]
    for key, value in config.items():
        args += ["-c", key + "=" + json.dumps(value)]
    env = {
        k: v
        for k, v in os.environ.items()
        if k in ("PATH", "HOME", "USER", "TMPDIR", "LANG", "CODEX_HOME")
    }
    manifest: dict[str, Any] = {
        "host": subprocess.check_output(["codex", "--version"], text=True).strip(),
        "model": "host default; no override supplied",
        "python": subprocess.check_output([str(python), "--version"], text=True).strip(),
        "source_revision": subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
        ).strip(),
        "source_dirty": bool(
            subprocess.check_output(
                ["git", "-C", str(repo), "status", "--porcelain"], text=True
            ).strip()
        ),
        "dependency_lock_sha256": hashlib.sha256((repo / "uv.lock").read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "suite_sha256": hashlib.sha256(suite.read_bytes()).hexdigest(),
        "context_sha256": hashlib.sha256(context.encode()).hexdigest(),
        "runtime_sha256": before,
        "mode": "injected Scout skills and real fixture MCP; native plugin activation untested",
        "rubric_sent_to_host": False,
        "cases": [],
    }
    for case in prompts:
        started = time.monotonic()
        identifier = case["id"]
        command = args + ["-o", str(output / f"{identifier}-answer.md"), "-"]
        code: int | str
        try:
            with (
                (output / f"{identifier}-events.jsonl").open("w") as log,
                (output / f"{identifier}-stderr.log").open("w") as err,
            ):
                completed = subprocess.run(
                    command,
                    input=case["prompt"],
                    text=True,
                    stdout=log,
                    stderr=err,
                    env=env,
                    timeout=240,
                )
                code = completed.returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
        manifest["cases"].append(
            {"id": identifier, "exit_code": code, "seconds": round(time.monotonic() - started, 1)}
        )
        manifest["runtime_unchanged"] = before == runtime_hash(repo)
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(json.dumps(manifest["cases"][-1]), flush=True)
        if not manifest["runtime_unchanged"]:
            raise RuntimeError("Candidate runtime changed during evaluation")
    if any(case["exit_code"] != 0 for case in manifest["cases"]):
        raise RuntimeError("One or more host sessions failed; inspect the manifest")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    args = parser.parse_args()
    run(args.suite.resolve(), args.repo.resolve(), args.output.resolve(), args.python.absolute())


if __name__ == "__main__":
    main()
