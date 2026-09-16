"""Smoke-test a built Scout wheel over real stdio MCP from a clean directory.

The server command runs with only PATH and a temporary HOME, from an empty temp
directory, so it cannot fall back to the source checkout, a repo fixture, or any
provider credential. Fails when package data is missing from the wheel.

Usage (from the repo root):
    python -m scripts.wheel_smoke --wheel dist/<wheel> -- <server command...>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from scripts.verify_advisory_mcp import EXPECTED

REQUIRED_WHEEL_DATA = (
    "scout_portfolio_manager/data/portfolio.json",
    "scout_portfolio_manager/data/price_history.json",
)
TIMEOUT_SECONDS = 30.0


def check_wheel(wheel: Path) -> list[str]:
    """Return package-data paths missing from the wheel."""
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    return [path for path in REQUIRED_WHEEL_DATA if path not in names]


async def smoke(command: list[str], home: Path, cwd: Path) -> dict[str, object]:
    params = StdioServerParameters(
        command=command[0],
        args=command[1:],
        env={"PATH": os.environ.get("PATH", os.defpath), "HOME": str(home)},
        cwd=str(cwd),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            if names != EXPECTED:
                raise AssertionError(f"tool registry mismatch: {sorted(names ^ EXPECTED)}")
            response = await session.call_tool("get_portfolio_snapshot", {})
            if response.isError:
                raise AssertionError(f"get_portfolio_snapshot failed: {response.content}")
            block = response.content[0]
            if block.type != "text":
                raise AssertionError("get_portfolio_snapshot returned non-text content")
            payload = json.loads(block.text)
    snapshot = payload.get("snapshot") or {}
    if payload.get("status") != "ok" or snapshot.get("source", {}).get("kind") != "fixture":
        raise AssertionError(f"unexpected snapshot: {payload}")
    if not snapshot.get("holdings"):
        raise AssertionError("packaged fixture returned no holdings")
    return {"tools": len(names), "source": snapshot["source"]["kind"]}


def _leaf_errors(exc: BaseException) -> list[BaseException]:
    if isinstance(exc, BaseExceptionGroup):
        return [leaf for inner in exc.exceptions for leaf in _leaf_errors(inner)]
    return [exc]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = [part for part in args.command if part != "--"]
    if not command:
        parser.error("a server command is required after --")

    missing = check_wheel(args.wheel)
    if missing:
        print(f"wheel is missing package data: {missing}", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as cwd:
        try:
            result = asyncio.run(
                asyncio.wait_for(smoke(command, Path(home), Path(cwd)), TIMEOUT_SECONDS)
            )
        except Exception as exc:  # noqa: BLE001 - any failure fails the smoke
            for cause in _leaf_errors(exc):
                print(f"wheel smoke failed: {type(cause).__name__}: {cause}", file=sys.stderr)
            return 1
    print(f"wheel smoke passed: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
