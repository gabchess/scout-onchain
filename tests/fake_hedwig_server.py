"""Fake Hedwig stdio MCP server for offline tests. No Node, no network.

Speaks the same newline-delimited JSON-RPC 2.0 framing the real server uses
and implements just enough policy logic (recipient allowlist, one per-action
USDC cap) to exercise Scout's preflight hook. Behavior is chosen by argv[1]:

    normal      answer `tools/call` against the policy file (the default)
    hang        never answer a `tools/call`, to exercise the read deadline
    exit        exit non-zero instead of answering a `tools/call`
    malformed   answer a `tools/call` with a line that is not JSON-RPC
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Mapping

MODE = sys.argv[1] if len(sys.argv) > 1 else "normal"


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
            if MODE == "hang":
                time.sleep(30)
                continue
            if MODE == "exit":
                sys.exit(1)
            if MODE == "malformed":
                sys.stdout.write("not json-rpc\n")
                sys.stdout.flush()
                continue
            arguments = (message.get("params") or {}).get("arguments") or {}
            result = _consult(arguments.get("request"), policy)
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(result)}],
                        "structuredContent": result,
                        "isError": False,
                    },
                }
            )
        else:
            error = {"code": -32601, "message": "not found"}
            _send({"jsonrpc": "2.0", "id": msg_id, "error": error})


if __name__ == "__main__":
    main()
