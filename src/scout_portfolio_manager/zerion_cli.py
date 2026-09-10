"""Explicitly enabled, pinned Zerion CLI transport for unsigned preparation only."""

from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .zerion_prepare import PreparationIntent, PreparationService

SUPPORTED_CLI_VERSION = "1.9.1"
MAX_OUTPUT = 1_048_576


def bounded_process(argv: list[str], env: Mapping[str, str], timeout: float = 30) -> str:
    """Bound both output streams and kill the process group on failure."""
    process = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=dict(env),
        start_new_session=True,
    )
    selector = selectors.DefaultSelector()
    assert process.stdout is not None and process.stderr is not None
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    output = bytearray()
    total = 0
    deadline = time.monotonic() + timeout
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Zerion preparation timed out")
            for key, _ in selector.select(min(remaining, 0.1)):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                total += len(chunk)
                if total > MAX_OUTPUT:
                    raise ValueError("Zerion output limit exceeded")
                if key.data == "stdout":
                    output.extend(chunk)
        process.wait(timeout=max(0.01, deadline - time.monotonic()))
        if process.returncode != 0:
            raise ValueError("Zerion preparation failed")
        return output.decode("utf-8")
    finally:
        # A child process could retain pipes or outlive the parent; close the whole group.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        selector.close()
        process.stdout.close()
        process.stderr.close()


class ZerionCliProvider:
    """The operator supplies the official executable. No package installation occurs."""

    def __init__(self, executable: Path, environ: Mapping[str, str]):
        if not executable.is_absolute():
            raise ValueError("Zerion CLI path must be absolute")
        resolved = executable.resolve(strict=True)
        if resolved.name != "zerion.js" or resolved.parent.name != "cli":
            raise ValueError("Point to the installed official zerion-cli/cli/zerion.js")
        package = json.loads((resolved.parent.parent / "package.json").read_text())
        if package.get("name") != "zerion-cli" or package.get("version") != SUPPORTED_CLI_VERSION:
            raise ValueError("Unsupported Zerion CLI package version; expected 1.9.1")
        if not os.access(resolved, os.X_OK):
            raise ValueError("Zerion CLI is not executable")
        self.executable = resolved
        # Host config remains operator-owned. Never forward wallet keys, agent tokens,
        # NODE_OPTIONS, arbitrary RPC overrides, or policy-bypass environment flags.
        self.env = {k: environ[k] for k in ("PATH", "HOME", "LANG") if environ.get(k)}
        if environ.get("ZPM_ZERION_PREPARE_API_KEY"):
            self.env["ZERION_API_KEY"] = environ["ZPM_ZERION_PREPARE_API_KEY"]
        if not self.env.get("ZERION_API_KEY"):
            raise ValueError("Preparation requires an explicitly supplied Zerion API key")

    def prepare(self, intent: PreparationIntent) -> dict[str, Any]:
        value = json.loads(bounded_process([str(self.executable), *intent.cli_args()], self.env))
        if not isinstance(value, dict):
            raise ValueError("Zerion response must be an object")
        return value


def preparation_from_env(environ: Mapping[str, str]) -> PreparationService:
    """Disabled by default, and never infer enablement from existing analytics keys."""
    flag = environ.get("ZPM_ZERION_PREPARE_ENABLED", "")
    if flag not in ("", "0", "1"):
        raise ValueError("ZPM_ZERION_PREPARE_ENABLED must be 0 or 1")
    if flag != "1":
        return PreparationService()
    path = Path(environ.get("ZPM_ZERION_PREPARE_STORE", ""))
    if not path.is_absolute():
        raise ValueError("ZPM_ZERION_PREPARE_STORE must be an absolute database path")
    provider = ZerionCliProvider(Path(environ.get("ZPM_ZERION_CLI_PATH", "")), environ)
    return PreparationService(provider, path)
