"""Fake Hedwig stdio MCP server for offline tests. No Node, no network.

Speaks the same newline-delimited JSON-RPC 2.0 framing the real server uses
and implements just enough policy logic (recipient allowlist, one per-action
USDC cap) to exercise Scout's preflight hook. `initialize` always answers
correctly; every mode below only changes how ONE `tools/call` is answered, so
each exercises one failure path in `HedwigClient` without also breaking the
handshake. Behavior is chosen by argv[1], optionally with a `:`-separated
parameter:

    normal            answer a `tools/call` correctly (the default)
    hang              never answer a `tools/call`, to exercise the deadline
    exit              exit non-zero instead of answering a `tools/call`
    malformed         answer with a line that is not JSON-RPC at all
    double_response   answer correctly, then send one extra stray ALLOW
                      response reusing the same id (the stale-pipe case)
    bad_id:999        answer with the wrong id (999)
    bad_id:null       answer with `id: null`
    bad_id:string     answer with the right id, but as a JSON string
    bad_id:missing    answer with no `id` key at all
    notify:N          send N JSON-RPC notifications before the real answer
    is_error          answer with `isError: true`
    missing_verdict   answer with `structuredContent` missing `verdict`
    bad_verdict       answer with `verdict: "MAYBE"`, not one of the three
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Mapping

_raw_mode = sys.argv[1] if len(sys.argv) > 1 else "normal"
MODE, _, MODE_PARAM = _raw_mode.partition(":")


def _read_policy() -> Mapping[str, Any]:
    path = os.environ.get("HEDWIG_POLICY_FILE", "")
    if not path:
        return {}
    with open(path) as handle:
        loaded = json.load(handle)
    return loaded if isinstance(loaded, dict) else {}


def _consult(request: Any, policy: Mapping[str, Any]) -> Mapping[str, Any]:
    action = (request or {}).get("action") or {}
    recipient = str(action.get("recipient") or "").lower()
    approved = {str(entry).lower() for entry in policy.get("approvedRecipients", [])}
    if recipient not in approved:
        return _result(
            False,
            "DENY",
            "recipient-matches-policy",
            "RECIPIENT_NOT_IN_POLICY",
            f"recipient {recipient} is not an approved policy entry",
        )
    cap = int(policy.get("perActionCaps", {}).get(action.get("type", ""), 0) or 0)
    amount = int(action.get("amount") or 0)
    if amount > cap:
        return _result(
            False,
            "DENY",
            "amount-within-cap",
            "AMOUNT_EXCEEDS_CAP",
            f"amount {amount} exceeds the cap {cap}",
        )
    return _result(
        True,
        "ALLOW_UNDER_POLICY",
        "amount-within-cap",
        "AMOUNT_WITHIN_CAP",
        f"amount {amount} is within the cap {cap}",
    )


def _result(
    proceed: bool, verdict: str, row_id: str, code: str, evidence: str
) -> Mapping[str, Any]:
    return {
        "question": "Should this agent proceed with this action under the owner's policy?",
        "proceed": proceed,
        "verdict": verdict,
        "support": 1.0 if proceed else 0.0,
        "band": "green" if proceed else "red",
        "results": [
            {
                "id": row_id,
                "question": "fake",
                "status": "PASS" if proceed else "FAIL",
                "code": code,
                "evidence": evidence,
                "evidenceClass": "owner-policy",
                "reference": "fake",
            }
        ],
        "floorIds": [row_id],
        "advisory": True,
    }


def _send(message: Mapping[str, Any]) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def _tool_response(msg_id: object, result: Mapping[str, Any]) -> dict[str, Any]:
    response: dict[str, Any] = {"jsonrpc": "2.0", "result": result}
    if msg_id != "__omit__":
        response["id"] = msg_id
    return response


def _consult_tool_result(consult_result: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(consult_result)}],
        "structuredContent": consult_result,
        "isError": False,
    }


def _handle_tools_call(
    msg_id: object, arguments: Mapping[str, Any], policy: Mapping[str, Any]
) -> None:
    if MODE == "hang":
        time.sleep(30)
        return
    if MODE == "exit":
        sys.exit(1)
    if MODE == "malformed":
        sys.stdout.write("not json-rpc\n")
        sys.stdout.flush()
        return

    consult_result = _consult(arguments.get("request"), policy)

    if MODE == "notify":
        for _ in range(int(MODE_PARAM or "0")):
            _send({"jsonrpc": "2.0", "method": "notifications/message", "params": {}})

    if MODE == "is_error":
        _send(_tool_response(msg_id, {"content": [], "isError": True}))
        return
    if MODE == "missing_verdict":
        broken = dict(consult_result)
        del broken["verdict"]
        _send(_tool_response(msg_id, _consult_tool_result(broken)))
        return
    if MODE == "bad_verdict":
        broken = dict(consult_result)
        broken["verdict"] = "MAYBE"
        _send(_tool_response(msg_id, _consult_tool_result(broken)))
        return

    if MODE == "bad_id":
        bad_id: object
        if MODE_PARAM == "999":
            bad_id = 999
        elif MODE_PARAM == "null":
            bad_id = None
        elif MODE_PARAM == "string":
            bad_id = str(msg_id)
        elif MODE_PARAM == "missing":
            bad_id = "__omit__"
        else:
            bad_id = msg_id
        _send(_tool_response(bad_id, _consult_tool_result(consult_result)))
        return

    # normal and double_response both answer correctly first.
    _send(_tool_response(msg_id, _consult_tool_result(consult_result)))
    if MODE == "double_response":
        stray_allow = _result(
            True, "ALLOW_UNDER_POLICY", "amount-within-cap", "AMOUNT_WITHIN_CAP", "stray"
        )
        _send(_tool_response(msg_id, _consult_tool_result(stray_allow)))


def main() -> None:
    policy = _read_policy()
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        message = json.loads(line)
        method = message.get("method")
        msg_id = message.get("id")
        if method == "initialize":
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "fake-hedwig", "version": "0.0.0"},
                    },
                }
            )
        elif method == "notifications/initialized":
            continue
        elif method == "tools/call":
            arguments = (message.get("params") or {}).get("arguments") or {}
            _handle_tools_call(msg_id, arguments, policy)
        else:
            error = {"code": -32601, "message": "not found"}
            _send({"jsonrpc": "2.0", "id": msg_id, "error": error})


if __name__ == "__main__":
    main()
