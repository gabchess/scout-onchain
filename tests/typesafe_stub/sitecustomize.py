"""Test-only: replace the TypeSafe transport inside a stdio server subprocess.

Loaded through PYTHONPATH by tests/test_typesafe_mcp.py. Never shipped.
"""

import json
import os

if os.environ.get("SCOUT_TEST_TYPESAFE_STUB") == "1":
    from scout_portfolio_manager import typesafe_intent

    def _stub(bearer, body, timeout):
        return {
            "answers": {
                "amount_usd": {
                    "type": "choice",
                    "choice": "$50",
                    "probabilities": {"$200": 0.03, "$50": 0.96, "none": 0.01},
                    "confidence": 0.95,
                },
                "complete": {"type": "noul", "noul": 0.97},
            },
            "echo_fields": sorted(json.loads(body)),
        }

    typesafe_intent._urllib_transport = _stub
