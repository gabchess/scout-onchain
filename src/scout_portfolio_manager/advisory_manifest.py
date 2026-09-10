"""Descriptors for Scout's bounded advisory tools on the direct host surface."""

from __future__ import annotations

from typing import Any

ADVISORY_TOOL_NAMES = (
    "get_portfolio_risk",
    "assess_defi_yield",
    "search_defi_knowledge",
    "plan_zerion_action",
    "prepare_zerion_transaction",
    "get_zerion_preparation",
)


def advisory_manifest(version: str) -> list[dict[str, Any]]:
    descriptors = [
        (
            "get_portfolio_risk",
            "Gross observed allocation, concentration and uniform USD shock.",
            {"shock_pct": {"type": "number", "minimum": -100, "maximum": 100, "default": -30}},
            [],
        ),
        (
            "assess_defi_yield",
            "Caller-supplied simple APR scenario; no live rates or compounding.",
            {
                name: {"type": "number"}
                for name in (
                    "principal_usd",
                    "base_apr_pct",
                    "reward_apr_pct",
                    "borrow_apr_pct",
                    "fees_usd",
                    "days",
                )
            },
            ["principal_usd", "base_apr_pct"],
        ),
        (
            "search_defi_knowledge",
            "Offline source-linked concepts and blockchain terminology.",
            {
                "query": {"type": "string", "minLength": 1, "maxLength": 500},
                "ecosystem": {"type": "string", "enum": ["ethereum", "solana", "cross-chain"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 8, "default": 5},
            },
            ["query"],
        ),
        (
            "plan_zerion_action",
            "Zerion-only action plan; no execution or signing is available.",
            {
                "action": {
                    "type": "string",
                    "enum": ["swap", "bridge", "stake", "transfer", "payment", "data_access"],
                },
                "asset": {"type": "string"},
                "amount": {"type": "number", "exclusiveMinimum": 0},
                "chain": {"type": "string"},
                "destination": {"type": "string"},
            },
            ["action"],
        ),
    ]
    descriptors.extend(
        [
            (
                "prepare_zerion_transaction",
                "Opt-in Zerion unsigned EVM preparation; never signs.",
                {
                    name: {"type": "string"}
                    for name in (
                        "request_id",
                        "action",
                        "chain",
                        "source_wallet",
                        "asset",
                        "amount",
                        "target_asset",
                        "destination",
                        "destination_chain",
                    )
                }
                | {
                    "slippage_bps": {"type": "integer", "minimum": 0, "maximum": 500, "default": 50}
                },
                ["request_id", "action", "chain", "source_wallet", "asset", "amount"],
            ),
            (
                "get_zerion_preparation",
                "Read local unsigned preparation state; no settlement claim.",
                {"request_id": {"type": "string"}},
                ["request_id"],
            ),
        ]
    )
    return [
        {
            "name": name,
            "version": version,
            "description": description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        }
        for name, description, properties, required in descriptors
    ]
