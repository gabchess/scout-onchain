"""Offline demo of Scout's Hedwig preflight, run against the real built server.

No signer key and no network call: this script builds the same guard,
budget, and Hedwig client the x402 source builds, and drives them through
five injected 402 fixtures. Exits non-zero if any frame's outcome does not
match what the frame expects. Writes the transcript to
``fixtures/x402/hedwig-demo-transcript.json``.

Usage:
    HEDWIG_SERVER_PATH=/path/to/hedwig/mcp/dist/server.js \\
        python scripts/hedwig_demo.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

from scout_portfolio_manager.hedwig_client import HedwigClient
from scout_portfolio_manager.x402_guard import BASE_NETWORK, BASE_USDC_ADDRESS, X402PaymentGuard
from scout_portfolio_manager.x402_source import (
    HEDWIG_SERVER_PATH_ENV,
    X402SpendBudget,
    build_hedwig_client,
    build_hedwig_policy_document,
    preflight_before_signing,
)
from scout_portfolio_manager.zerion_api import ZerionConfigError

REPO_ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT_PATH = REPO_ROOT / "fixtures" / "x402" / "hedwig-demo-transcript.json"

#: Fixed demo addresses. Placeholders, not real wallets.
PAY_TO = "0x1111111111111111111111111111111111111111"
OTHER_RECIPIENT = "0x2222222222222222222222222222222222222222"

SCOUT_MAX_USD_PER_CALL = "$0.05"
#: build_hedwig_client always mirrors Scout's own cap into Hedwig's policy,
#: so in normal operation these two caps are identical. This demo passes a
#: DIFFERENT, stricter value here on purpose, standing in for an operator
#: who edited the generated Hedwig policy file afterward to tighten it
#: further. That is the only way the "stricter_owner_policy" frame below can
#: happen; Scout's own wiring cannot produce it by itself.
HEDWIG_MAX_USD_PER_CALL = "$0.04"


def _fixture(*, amount: str, pay_to: str = PAY_TO, timeout: int = 60) -> SimpleNamespace:
    requirements = SimpleNamespace(
        network=BASE_NETWORK,
        asset=BASE_USDC_ADDRESS,
        amount=amount,
        scheme="exact",
        pay_to=pay_to,
        max_timeout_seconds=timeout,
        get_amount=lambda: amount,
    )
    return SimpleNamespace(selected_requirements=requirements)


def _run_frame(
    name: str,
    *,
    context: SimpleNamespace,
    guard: X402PaymentGuard,
    budget: X402SpendBudget,
    hedwig_client: Optional[HedwigClient],
    expect: str,
) -> dict[str, Any]:
    try:
        preflight_before_signing(
            context, guard=guard, spend_budget=budget, hedwig_client=hedwig_client
        )
    except Exception as exc:  # noqa: BLE001 - the demo prints whatever Scout raised
        outcome = "blocked"
        detail: Optional[str] = str(exc)
    else:
        outcome = "allowed"
        detail = None
        if hedwig_client is not None:
            # Display-only: guard and Hedwig already both passed, so this
            # extra call cannot change the reservation Scout already made.
            # ALLOW_UNDER_POLICY only happens when every row passed, so
            # naming a "worst" row here would read like a failure; there
            # isn't one.
            try:
                answer = hedwig_client.consult_payment(context.selected_requirements)
                detail = f"verdict={answer.verdict} all rows PASS"
            except Exception:  # noqa: BLE001 - purely cosmetic
                detail = None

    reservations_after = budget.status()["reserved_payments"]
    suffix = f" {detail}" if detail else ""
    print(f"[{name}] outcome={outcome} reservations={reservations_after}{suffix}")
    frame: dict[str, Any] = {
        "name": name,
        "outcome": outcome,
        "reservations_after": reservations_after,
    }
    if detail:
        frame["detail"] = detail
    if outcome != expect:
        print(f"[{name}] FAILED: expected {expect}, got {outcome}", file=sys.stderr)
        sys.exit(1)
    return frame


def main() -> int:
    server_path = (os.environ.get(HEDWIG_SERVER_PATH_ENV) or "").strip()
    if not server_path:
        print(f"set {HEDWIG_SERVER_PATH_ENV} to a built Hedwig mcp/dist/server.js", file=sys.stderr)
        return 1

    guard = X402PaymentGuard.from_usd(SCOUT_MAX_USD_PER_CALL, pay_to=PAY_TO)
    budget = X402SpendBudget.from_strings(SCOUT_MAX_USD_PER_CALL, "$5.00")
    # PATH/HOME come from the real environment so the child finds `node`;
    # build_hedwig_client's own allowlist decides what reaches the child.
    try:
        hedwig_client = build_hedwig_client(
            {**os.environ, HEDWIG_SERVER_PATH_ENV: server_path},
            pay_to=PAY_TO,
            max_usd_per_call=HEDWIG_MAX_USD_PER_CALL,
        )
    except ZerionConfigError as exc:
        print(f"Hedwig client did not build: {exc}", file=sys.stderr)
        return 1
    if hedwig_client is None:
        print("Hedwig client did not build", file=sys.stderr)
        return 1

    policy = build_hedwig_policy_document(pay_to=PAY_TO, max_usd_per_call=HEDWIG_MAX_USD_PER_CALL)
    agent_cap = X402PaymentGuard.from_usd(SCOUT_MAX_USD_PER_CALL, pay_to=PAY_TO)
    agent_cap_atomic = int(agent_cap.max_usd_per_payment * 10**6)
    owner_policy_cap = policy["perActionCaps"]["pay"]
    owner_policy_cap_note = (
        f'owner_policy_cap: "{owner_policy_cap}" (set by the owner in the '
        f'Hedwig policy, below the agent\'s own cap of "{agent_cap_atomic}")'
    )
    print(
        f"config: scout_max_usd_per_call={SCOUT_MAX_USD_PER_CALL} "
        f"hedwig_max_usd_per_call={HEDWIG_MAX_USD_PER_CALL}"
    )
    print(owner_policy_cap_note)
    print(f"derived policy: {json.dumps(policy)}")

    frames: list[dict[str, Any]] = [
        {
            "name": "config",
            "outcome": "printed",
            "policy": policy,
            "owner_policy_cap": owner_policy_cap,
            "agent_own_cap": str(agent_cap_atomic),
            "note": owner_policy_cap_note,
        }
    ]

    frames.append(
        _run_frame(
            "good_pay",
            context=_fixture(amount="30000"),
            guard=guard,
            budget=budget,
            hedwig_client=hedwig_client,
            expect="allowed",
        )
    )
    frames.append(
        _run_frame(
            "swapped_pay_to",
            context=_fixture(amount="30000", pay_to=OTHER_RECIPIENT),
            guard=guard,
            budget=budget,
            hedwig_client=hedwig_client,
            expect="blocked",
        )
    )
    frames.append(
        _run_frame(
            "stricter_owner_policy",
            context=_fixture(amount="45000"),
            guard=guard,
            budget=budget,
            hedwig_client=hedwig_client,
            expect="blocked",
        )
    )

    print("killing the Hedwig server to simulate it disappearing mid-session")
    child = hedwig_client._process  # noqa: SLF001 - deliberate, for this frame only
    # build_hedwig_client's own version-handshake consult already forced a
    # real spawn before this script ever ran a frame.
    assert child is not None, "build_hedwig_client's handshake should have already spawned it"
    child.kill()
    child.wait(timeout=2)

    frames.append(
        _run_frame(
            "server_killed",
            context=_fixture(amount="30000"),
            guard=guard,
            budget=budget,
            hedwig_client=hedwig_client,
            expect="blocked",
        )
    )

    transcript = {
        "scout_max_usd_per_call": SCOUT_MAX_USD_PER_CALL,
        "hedwig_max_usd_per_call": HEDWIG_MAX_USD_PER_CALL,
        "frames": frames,
    }
    TRANSCRIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRANSCRIPT_PATH.write_text(json.dumps(transcript, indent=2) + "\n")
    print(f"wrote {TRANSCRIPT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
