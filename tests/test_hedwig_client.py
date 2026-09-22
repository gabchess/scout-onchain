"""Tests for the Hedwig second-opinion preflight hook.

Offline by construction: real-protocol cases spawn `tests/fake_hedwig_server.py`
with ``sys.executable``, never Node, so CI needs no Node runtime. One test
opts into the real built Hedwig server and is skipped unless
``HEDWIG_SERVER_PATH`` names it.
"""

from __future__ import annotations

import dataclasses
import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scout_portfolio_manager.hedwig_client import (
    CHILD_ENV_ALLOWLIST,
    ConsultAnswer,
    HedwigClient,
    _child_environment,
)
from scout_portfolio_manager.x402_guard import BASE_NETWORK, BASE_USDC_ADDRESS, X402PaymentGuard
from scout_portfolio_manager.x402_source import (
    HEDWIG_SERVER_PATH_ENV,
    X402SpendBudget,
    build_hedwig_client,
    build_hedwig_policy_document,
    hedwig_policy_cap_atomic,
    preflight_before_signing,
    write_hedwig_policy_file,
)
from scout_portfolio_manager.zerion_api import ZerionAPIPaymentError

FAKE_SERVER = Path(__file__).resolve().parent / "fake_hedwig_server.py"

PINNED = "0x1111111111111111111111111111111111111111"
ATTACKER = "0x2222222222222222222222222222222222222222"

#: Deadlines short enough that the timeout test does not slow the suite down.
FAST_SPAWN_DEADLINE = 2.0
FAST_CALL_DEADLINE = 0.3


def fake_client(mode: str = "normal", *, policy_file: str, **kwargs: object) -> HedwigClient:
    return HedwigClient(
        [sys.executable, str(FAKE_SERVER), mode],
        policy_file=policy_file,
        spawn_deadline=FAST_SPAWN_DEADLINE,
        call_deadline=FAST_CALL_DEADLINE,
        **kwargs,
    )


def hedwig_payment_context(
    *,
    network: str = BASE_NETWORK,
    asset: str = BASE_USDC_ADDRESS,
    amount: str = "30000",
    pay_to: str = PINNED,
    timeout: int = 60,
    scheme: str = "exact",
) -> SimpleNamespace:
    requirements = SimpleNamespace(
        network=network,
        asset=asset,
        amount=amount,
        scheme=scheme,
        pay_to=pay_to,
        max_timeout_seconds=timeout,
        get_amount=lambda: amount,
    )
    return SimpleNamespace(selected_requirements=requirements)


# --- ConsultAnswer shape -----------------------------------------------------


def test_consult_answer_has_no_support_or_band_fields():
    field_names = {field.name for field in dataclasses.fields(ConsultAnswer)}
    assert field_names == {
        "proceed",
        "verdict",
        "worst_row_id",
        "worst_row_code",
        "worst_row_evidence",
    }


# --- env allowlist ------------------------------------------------------------


def test_child_environment_allowlists_only_path_and_home():
    environ = {"PATH": "/bin", "HOME": "/tmp", "CANARY_SECRET": "leak-me"}
    child = _child_environment(environ, "/tmp/policy.json")
    assert child == {"PATH": "/bin", "HOME": "/tmp", "HEDWIG_POLICY_FILE": "/tmp/policy.json"}
    assert "CANARY_SECRET" not in child
    assert set(CHILD_ENV_ALLOWLIST) == {"PATH", "HOME"}


def test_child_environment_omits_policy_file_when_none():
    child = _child_environment({"PATH": "/bin"}, None)
    assert "HEDWIG_POLICY_FILE" not in child


# --- policy derivation ---------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("$0.05", "50000"),
        ("$1", "1000000"),
        ("$0.0000015", "1"),  # floors 1.5 atomic units down to 1, never up
        ("$0.000001", "1"),
    ],
)
def test_hedwig_policy_cap_is_floored_never_rounded_up(value, expected):
    assert hedwig_policy_cap_atomic(value) == expected


def test_hedwig_policy_document_shape():
    document = build_hedwig_policy_document(pay_to=PINNED, max_usd_per_call="$0.05")
    assert document == {
        "permits": True,
        "chainId": BASE_NETWORK,
        "approvedRecipients": [PINNED],
        "perActionCaps": {"pay": "50000"},
        "role": {"mode": "not-required"},
    }


def test_write_hedwig_policy_file_is_owner_only(tmp_path, monkeypatch):
    import tempfile

    monkeypatch.setattr(tempfile, "mkdtemp", lambda prefix="": str(tmp_path / "hedwig"))
    os.makedirs(tmp_path / "hedwig", exist_ok=True)
    policy_path, policy_dir = write_hedwig_policy_file(pay_to=PINNED, max_usd_per_call="$0.05")
    mode = stat.S_IMODE(os.stat(policy_path).st_mode)
    assert mode == 0o600
    assert policy_dir in policy_path


# --- build_hedwig_client gating ------------------------------------------------


def test_build_hedwig_client_is_none_without_server_path():
    assert build_hedwig_client({}, pay_to=PINNED, max_usd_per_call="$0.05") is None


def test_build_hedwig_client_is_none_without_pay_to():
    environ = {HEDWIG_SERVER_PATH_ENV: "/some/server.js"}
    assert build_hedwig_client(environ, pay_to=None, max_usd_per_call="$0.05") is None
    assert build_hedwig_client(environ, pay_to="", max_usd_per_call="$0.05") is None


def test_build_hedwig_client_builds_when_configured(tmp_path, monkeypatch):
    import scout_portfolio_manager.x402_source as x402_source_module

    monkeypatch.setattr(x402_source_module.atexit, "register", lambda *a, **k: None)
    environ = {HEDWIG_SERVER_PATH_ENV: str(FAKE_SERVER)}
    client = build_hedwig_client(environ, pay_to=PINNED, max_usd_per_call="$0.05")
    assert isinstance(client, HedwigClient)


# --- the eight offline preflight cases -----------------------------------------


def test_good_pay_allows_and_reserves_budget(tmp_path):
    policy_path, _ = write_hedwig_policy_file(pay_to=PINNED, max_usd_per_call="$0.05")
    client = fake_client(policy_file=policy_path)
    guard = X402PaymentGuard.from_usd("$0.05", pay_to=PINNED)
    budget = X402SpendBudget.from_strings("$0.05", "$0.10")

    preflight_before_signing(
        hedwig_payment_context(amount="30000"),
        guard=guard,
        spend_budget=budget,
        hedwig_client=client,
    )

    assert budget.status()["reserved_payments"] == 1
    client.close()


def test_swapped_pay_to_scout_guard_refuses_before_hedwig_is_ever_called():
    class PoisonHedwigClient:
        def __init__(self):
            self.calls = 0

        def consult_payment(self, requirements):
            self.calls += 1
            raise AssertionError("Hedwig must not be called when Scout's guard already refused")

    poison = PoisonHedwigClient()
    guard = X402PaymentGuard.from_usd("$0.05", pay_to=PINNED)
    budget = X402SpendBudget.from_strings("$0.05", "$0.10")

    with pytest.raises(ZerionAPIPaymentError, match="pay_to_not_allowed"):
        preflight_before_signing(
            hedwig_payment_context(pay_to=ATTACKER),
            guard=guard,
            spend_budget=budget,
            hedwig_client=poison,
        )

    assert poison.calls == 0
    assert budget.status()["reserved_payments"] == 0


def test_unknown_recipient_reaching_hedwig_is_denied():
    # Scout's own guard accepts PINNED; Hedwig's own policy approves a
    # different address, so Hedwig denies what Scout already let through.
    policy_path, _ = write_hedwig_policy_file(pay_to=ATTACKER, max_usd_per_call="$0.05")
    client = fake_client(policy_file=policy_path)
    guard = X402PaymentGuard.from_usd("$0.05", pay_to=PINNED)
    budget = X402SpendBudget.from_strings("$0.05", "$0.10")

    with pytest.raises(ZerionAPIPaymentError, match="hedwig_deny"):
        preflight_before_signing(
            hedwig_payment_context(amount="30000"),
            guard=guard,
            spend_budget=budget,
            hedwig_client=client,
        )

    assert budget.status()["reserved_payments"] == 0
    client.close()


def test_cap_exceeded_at_hedwig_but_not_at_scout():
    # Hedwig's policy cap ($0.04 = 40000) is stricter than Scout's own ($0.05
    # = 50000). An amount of 45000 clears Scout's guard and hits Hedwig's cap.
    policy_path, _ = write_hedwig_policy_file(pay_to=PINNED, max_usd_per_call="$0.04")
    client = fake_client(policy_file=policy_path)
    guard = X402PaymentGuard.from_usd("$0.05", pay_to=PINNED)
    budget = X402SpendBudget.from_strings("$0.05", "$0.10")

    with pytest.raises(ZerionAPIPaymentError, match="hedwig_deny"):
        preflight_before_signing(
            hedwig_payment_context(amount="45000"),
            guard=guard,
            spend_budget=budget,
            hedwig_client=client,
        )

    assert budget.status()["reserved_payments"] == 0
    client.close()


def test_timeout_marks_client_permanently_unavailable():
    policy_path, _ = write_hedwig_policy_file(pay_to=PINNED, max_usd_per_call="$0.05")
    client = fake_client("hang", policy_file=policy_path)
    guard = X402PaymentGuard.from_usd("$0.05", pay_to=PINNED)
    budget = X402SpendBudget.from_strings("$0.05", "$0.10")
    context = hedwig_payment_context(amount="30000")

    with pytest.raises(ZerionAPIPaymentError, match="hedwig_unavailable"):
        preflight_before_signing(context, guard=guard, spend_budget=budget, hedwig_client=client)
    assert budget.status()["reserved_payments"] == 0

    # The next call must fail immediately (no second hang, no respawn), and
    # must never resynchronise a pipe that might still hold the first answer.
    with pytest.raises(ZerionAPIPaymentError, match="hedwig_unavailable"):
        preflight_before_signing(context, guard=guard, spend_budget=budget, hedwig_client=client)
    assert budget.status()["reserved_payments"] == 0
    client.close()


def test_non_zero_exit_marks_client_unavailable():
    policy_path, _ = write_hedwig_policy_file(pay_to=PINNED, max_usd_per_call="$0.05")
    client = fake_client("exit", policy_file=policy_path)
    guard = X402PaymentGuard.from_usd("$0.05", pay_to=PINNED)
    budget = X402SpendBudget.from_strings("$0.05", "$0.10")

    with pytest.raises(ZerionAPIPaymentError, match="hedwig_unavailable"):
        preflight_before_signing(
            hedwig_payment_context(amount="30000"),
            guard=guard,
            spend_budget=budget,
            hedwig_client=client,
        )
    assert budget.status()["reserved_payments"] == 0
    client.close()


def test_malformed_json_marks_client_unavailable():
    policy_path, _ = write_hedwig_policy_file(pay_to=PINNED, max_usd_per_call="$0.05")
    client = fake_client("malformed", policy_file=policy_path)
    guard = X402PaymentGuard.from_usd("$0.05", pay_to=PINNED)
    budget = X402SpendBudget.from_strings("$0.05", "$0.10")

    with pytest.raises(ZerionAPIPaymentError, match="hedwig_unavailable"):
        preflight_before_signing(
            hedwig_payment_context(amount="30000"),
            guard=guard,
            spend_budget=budget,
            hedwig_client=client,
        )
    assert budget.status()["reserved_payments"] == 0
    client.close()


def test_missing_server_path_never_installs_the_hook():
    # HEDWIG_SERVER_PATH unset: build_hedwig_client returns None, so the
    # hook is never installed and Scout's guard/budget behave exactly as
    # they did before Hedwig existed.
    assert build_hedwig_client({}, pay_to=PINNED, max_usd_per_call="$0.05") is None
    guard = X402PaymentGuard.from_usd("$0.05", pay_to=PINNED)
    budget = X402SpendBudget.from_strings("$0.05", "$0.10")

    preflight_before_signing(
        hedwig_payment_context(amount="30000"),
        guard=guard,
        spend_budget=budget,
        hedwig_client=None,
    )

    assert budget.status()["reserved_payments"] == 1


# --- opt-in real server ---------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get(HEDWIG_SERVER_PATH_ENV),
    reason=f"set {HEDWIG_SERVER_PATH_ENV} to a built Hedwig mcp/dist/server.js to run this test",
)
def test_real_hedwig_server_allows_and_denies():
    server_path = os.environ[HEDWIG_SERVER_PATH_ENV]
    # PATH and HOME come from the real environment so the child can find the
    # real `node` binary; build_hedwig_client's own allowlist still decides
    # what actually reaches the child process.
    client = build_hedwig_client(
        {**os.environ, HEDWIG_SERVER_PATH_ENV: server_path},
        pay_to=PINNED,
        max_usd_per_call="$0.05",
    )
    assert client is not None
    guard = X402PaymentGuard.from_usd("$0.05", pay_to=PINNED)
    budget = X402SpendBudget.from_strings("$0.05", "$0.10")

    preflight_before_signing(
        hedwig_payment_context(amount="30000"),
        guard=guard,
        spend_budget=budget,
        hedwig_client=client,
    )
    assert budget.status()["reserved_payments"] == 1

    with pytest.raises(ZerionAPIPaymentError, match="hedwig_deny"):
        preflight_before_signing(
            hedwig_payment_context(amount="30000", pay_to=ATTACKER),
            guard=X402PaymentGuard.from_usd("$0.05", pay_to=ATTACKER),
            spend_budget=budget,
            hedwig_client=client,
        )
    assert budget.status()["reserved_payments"] == 1
    client.close()
