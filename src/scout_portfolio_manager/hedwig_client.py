"""Stdlib-only client for Hedwig's stdio MCP `consult` tool.

Hedwig (https://github.com/gabchess/hedwig) is a standalone policy engine
Scout can ask for a second opinion on a payment before it signs. This client
spawns a Node child once, lazily, on the first call, and speaks the same
newline-delimited JSON-RPC 2.0 framing the MCP stdio transport uses: no
Content-Length headers, one JSON object per line.

Fails closed by construction: a timeout, a parse error, a non-zero exit, or a
broken pipe kills the child and marks this client permanently unavailable,
for the rest of the process, so a stale response already sitting in the pipe
can never be read as the answer to a later call. There is no later call:
every call after the first failure raises immediately without touching the
pipe again.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

#: Deadline for the initialize handshake when the child is first spawned.
DEFAULT_SPAWN_DEADLINE_SECONDS = 5.0
#: Deadline for one consult call once the child is already running.
DEFAULT_CALL_DEADLINE_SECONDS = 2.0

#: Names copied from the caller's environment into the child's, and nothing
#: else. A secret sitting in this process's environment under any other name
#: never reaches the child.
CHILD_ENV_ALLOWLIST = ("PATH", "HOME")
HEDWIG_POLICY_FILE_ENV = "HEDWIG_POLICY_FILE"

_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_NAME = "scout-hedwig-preflight"
_CLIENT_VERSION = "0.1.0"
_TOOL_NAME = "consult"


class HedwigUnavailable(Exception):
    """Hedwig cannot be consulted right now.

    Raised when no server path is configured at call time, the child failed
    to start or exited, its pipe broke, or an earlier failure already marked
    this client permanently unavailable.
    """


class HedwigTimeout(Exception):
    """A call to Hedwig did not answer inside its deadline."""


class HedwigProtocolError(Exception):
    """Hedwig's response was not usable: bad JSON-RPC, a missing field, or a
    tool result with ``isError`` set."""


@dataclass(frozen=True)
class ConsultAnswer:
    """The only shape Scout is allowed to branch on.

    No ``support`` and no ``band``: those are parsed away at this boundary on
    purpose, so nothing downstream of this client can branch on a score.
    ``worst_row_id``/``worst_row_code``/``worst_row_evidence`` come from
    Hedwig's ``results[0]``, which Hedwig itself sorts worst first.
    """

    proceed: bool
    verdict: str
    worst_row_id: Optional[str]
    worst_row_code: Optional[str]
    worst_row_evidence: Optional[str]


def _attr(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def map_payment_requirements(requirements: Any) -> Mapping[str, Any]:
    """Map the x402 SDK's selected requirements to a Hedwig ``pay`` request.

    v2 field names (snake_case); ``get_amount()`` also covers v1, since both
    expose it. Nothing beyond these fields is ever sent to Hedwig.
    """
    asset = _attr(requirements, "asset")
    amount = requirements.get_amount()
    return {
        "action": {
            "type": "pay",
            "chainId": _attr(requirements, "network"),
            "recipient": _attr(requirements, "pay_to"),
            "asset": {"symbol": "USDC", "contractAddress": asset},
            "amount": amount,
            "target": asset,
        }
    }


def _child_environment(
    environ: Mapping[str, str], policy_file: Optional[str]
) -> dict[str, str]:
    child = {name: environ[name] for name in CHILD_ENV_ALLOWLIST if name in environ}
    if policy_file is not None:
        child[HEDWIG_POLICY_FILE_ENV] = policy_file
    return child


def _parse_text_content(result: Mapping[str, Any]) -> Mapping[str, Any]:
    content = result.get("content")
    if not isinstance(content, list) or not content:
        raise HedwigProtocolError("Hedwig tool result had no structuredContent or content")
    first = content[0]
    text = first.get("text") if isinstance(first, Mapping) else None
    if not isinstance(text, str):
        raise HedwigProtocolError("Hedwig tool result content was not text")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HedwigProtocolError(f"Hedwig tool result text was not JSON: {exc}") from None
    if not isinstance(parsed, Mapping):
        raise HedwigProtocolError("Hedwig tool result text was not a JSON object")
    return parsed


def _str_or_none(row: Mapping[str, Any], key: str) -> Optional[str]:
    value = row.get(key)
    return value if isinstance(value, str) else None


def _parse_consult_answer(result: Mapping[str, Any]) -> ConsultAnswer:
    if not isinstance(result, Mapping):
        raise HedwigProtocolError("Hedwig tool result was not an object")
    if result.get("isError"):
        raise HedwigProtocolError(f"Hedwig tool call reported an error: {result}")
    structured = result.get("structuredContent")
    if not isinstance(structured, Mapping):
        structured = _parse_text_content(result)
    proceed = structured.get("proceed")
    verdict = structured.get("verdict")
    if not isinstance(proceed, bool) or not isinstance(verdict, str):
        raise HedwigProtocolError("Hedwig response is missing proceed or verdict")
    results = structured.get("results")
    worst = results[0] if isinstance(results, list) and results else None
    return ConsultAnswer(
        proceed=proceed,
        verdict=verdict,
        worst_row_id=_str_or_none(worst, "id") if isinstance(worst, Mapping) else None,
        worst_row_code=_str_or_none(worst, "code") if isinstance(worst, Mapping) else None,
        worst_row_evidence=_str_or_none(worst, "evidence") if isinstance(worst, Mapping) else None,
    )


class HedwigClient:
    """Speaks JSON-RPC to one lazily spawned Hedwig stdio MCP server.

    ``command`` is the argv to spawn (production: ``["node", server_path]``);
    tests inject a different command so no Node process is ever required in
    CI. The child is reused across calls once it starts cleanly. Any
    anomaly kills it and marks the client permanently unavailable: it never
    tries to respawn or to read a pipe that might still hold an old answer.
    """

    def __init__(
        self,
        command: Sequence[str],
        *,
        policy_file: Optional[str] = None,
        environ: Optional[Mapping[str, str]] = None,
        spawn_deadline: float = DEFAULT_SPAWN_DEADLINE_SECONDS,
        call_deadline: float = DEFAULT_CALL_DEADLINE_SECONDS,
    ) -> None:
        self._command = list(command)
        self._policy_file = policy_file
        self._environ = environ
        self._spawn_deadline = spawn_deadline
        self._call_deadline = call_deadline
        self._lock = threading.Lock()
        self._process: Optional["subprocess.Popen[bytes]"] = None
        self._responses: "queue.Queue[bytes]" = queue.Queue()
        self._unavailable = False
        self._next_id = 1

    def consult_payment(self, requirements: Any) -> ConsultAnswer:
        """Ask Hedwig's second opinion on one selected payment requirement."""
        request = map_payment_requirements(requirements)
        with self._lock:
            if self._unavailable:
                raise HedwigUnavailable("Hedwig client is permanently unavailable")
            if self._process is None:
                self._spawn_locked()
            result = self._call_locked(
                "tools/call", {"name": _TOOL_NAME, "arguments": {"request": request}}
            )
        return _parse_consult_answer(result)

    def close(self) -> None:
        """Best-effort shutdown; never raises. Safe to call more than once."""
        with self._lock:
            self._kill_locked()

    # -- internals; every method below assumes self._lock is held ----------

    def _spawn_locked(self) -> None:
        base_environ = self._environ if self._environ is not None else os.environ
        child_env = _child_environment(base_environ, self._policy_file)
        try:
            process = subprocess.Popen(
                self._command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=child_env,
            )
        except OSError as exc:
            self._unavailable = True
            raise HedwigUnavailable(f"could not start the Hedwig server: {exc}") from None
        self._process = process
        self._responses = queue.Queue()
        thread = threading.Thread(target=self._read_loop, args=(process,), daemon=True)
        thread.start()
        try:
            self._send_locked(
                {
                    "jsonrpc": "2.0",
                    "id": self._take_id(),
                    "method": "initialize",
                    "params": {
                        "protocolVersion": _PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {"name": _CLIENT_NAME, "version": _CLIENT_VERSION},
                    },
                }
            )
            self._read_locked(self._spawn_deadline)
            self._send_locked({"jsonrpc": "2.0", "method": "notifications/initialized"})
        except (HedwigTimeout, HedwigProtocolError, HedwigUnavailable):
            self._kill_locked()
            self._unavailable = True
            raise

    def _read_loop(self, process: "subprocess.Popen[bytes]") -> None:
        stdout = process.stdout
        assert stdout is not None
        try:
            for line in iter(stdout.readline, b""):
                self._responses.put(line)
        except (OSError, ValueError):
            pass
        finally:
            self._responses.put(b"")

    def _send_locked(self, message: Mapping[str, Any]) -> None:
        assert self._process is not None and self._process.stdin is not None
        try:
            payload = (json.dumps(message) + "\n").encode("utf-8")
            self._process.stdin.write(payload)
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise HedwigUnavailable(f"Hedwig pipe broke while sending: {exc}") from None

    def _read_locked(self, deadline: float) -> Mapping[str, Any]:
        try:
            line = self._responses.get(timeout=deadline)
        except queue.Empty:
            raise HedwigTimeout("Hedwig did not answer inside its deadline") from None
        if not line:
            code = self._process.poll() if self._process is not None else None
            raise HedwigUnavailable(f"Hedwig server pipe closed (exit code {code})")
        try:
            message = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HedwigProtocolError(f"Hedwig sent an unparsable line: {exc}") from None
        if not isinstance(message, Mapping) or message.get("jsonrpc") != "2.0":
            raise HedwigProtocolError("Hedwig response was not a JSON-RPC 2.0 message")
        if "error" in message:
            raise HedwigProtocolError(f"Hedwig returned a JSON-RPC error: {message['error']}")
        result = message.get("result")
        if not isinstance(result, Mapping):
            raise HedwigProtocolError("Hedwig response had no result")
        return result

    def _call_locked(self, method: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        try:
            self._send_locked(
                {"jsonrpc": "2.0", "id": self._take_id(), "method": method, "params": params}
            )
            return self._read_locked(self._call_deadline)
        except (HedwigTimeout, HedwigProtocolError, HedwigUnavailable):
            self._kill_locked()
            self._unavailable = True
            raise

    def _take_id(self) -> int:
        current = self._next_id
        self._next_id += 1
        return current

    def _kill_locked(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=1.0)
        except Exception:
            pass
        for stream in (process.stdin, process.stdout):
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass


__all__ = [
    "CHILD_ENV_ALLOWLIST",
    "ConsultAnswer",
    "HedwigClient",
    "HedwigProtocolError",
    "HedwigTimeout",
    "HedwigUnavailable",
    "HEDWIG_POLICY_FILE_ENV",
    "map_payment_requirements",
]
