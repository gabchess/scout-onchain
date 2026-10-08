"""Explicit hosted tool schemas. Runtime wire validation belongs to the hosted client."""

from copy import deepcopy
from typing import Annotated, Any

from pydantic import WithJsonSchema

HEDWIG_TOOL_NAMES = ("assess_with_hedwig", "get_hedwig_report")


def _object(properties: dict[str, Any], optional: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": [key for key in properties if key not in optional],
        "additionalProperties": False,
    }


_ADDRESS = {"type": "string", "pattern": "^0x[0-9a-fA-F]{40}$"}
_AMOUNT = {"type": "string", "pattern": "^(0|[1-9][0-9]*)$", "maxLength": 78}
_HASH = {"type": "string", "pattern": "^[a-f0-9]{64}$"}
_INTEGER = {"type": "integer", "minimum": 0, "maximum": 9007199254740991}
ASSESSMENT_BODY_SCHEMA = _object(
    {
        "version": {"type": "integer", "const": 1},
        "request": _object(
            {
                "chainId": {"type": "string", "const": "eip155:143"},
                "action": {"type": "string", "const": "swap"},
                "transaction": _object(
                    {
                        "from": _ADDRESS,
                        "to": _ADDRESS,
                        "data": {
                            "type": "string",
                            "pattern": "^0x([0-9a-fA-F]{2})+$",
                            "maxLength": 16384,
                        },
                        "value": _AMOUNT,
                    }
                ),
                "contracts": _object({"target": _ADDRESS, "token_out": _ADDRESS}),
                "amounts": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 1,
                    "items": _object(
                        {
                            "asset": {"type": "string", "const": "MON"},
                            "amount": _AMOUNT,
                            "direction": {"type": "string", "const": "in"},
                        }
                    ),
                },
                "setup": _object(
                    {
                        "slippageBps": {"type": "integer", "minimum": 0, "maximum": 10000},
                        "deadline": {**_INTEGER, "minimum": 1},
                    }
                ),
                "swapIntent": _object(
                    {
                        "tokenIn": _object(
                            {
                                "kind": {"type": "string", "const": "native"},
                                "symbol": {"type": "string", "const": "MON"},
                            }
                        ),
                        "tokenOutSymbol": {"type": "string", "const": "USDC"},
                        "recipient": _ADDRESS,
                        "quotedOut": _AMOUNT,
                        "minOut": _AMOUNT,
                        "approvalAmount": {"type": "string", "const": "0"},
                    }
                ),
                "question": {"type": "string", "maxLength": 2000},
            },
            ("question",),
        ),
    }
)
REFERENCE_SCHEMA = _object(
    {"handle": _HASH, "requestDigest": _HASH, "expiresAt": _INTEGER}, ("expiresAt",)
)
HedwigAssessmentBody = Annotated[dict[str, Any], WithJsonSchema(ASSESSMENT_BODY_SCHEMA)]
HedwigReference = Annotated[dict[str, Any], WithJsonSchema(REFERENCE_SCHEMA)]


def hedwig_manifest(version: str) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "version": version,
            "description": description,
            "inputSchema": {
                "type": "object",
                "properties": {argument: deepcopy(schema)},
                "required": [argument],
            },
        }
        for name, description, argument, schema in (
            (
                "assess_with_hedwig",
                "Assess one unsigned Monad proposal; no execution.",
                "body",
                ASSESSMENT_BODY_SCHEMA,
            ),
            (
                "get_hedwig_report",
                "Read the owner's saved Hedwig report; no reassessment.",
                "reference",
                REFERENCE_SCHEMA,
            ),
        )
    ]
