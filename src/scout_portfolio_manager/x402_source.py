"""Optional x402 pay-per-call source for the read-only Zerion adapter.

x402 (https://x402.org) is an open pay-per-request HTTP protocol. Instead of
an API key, the client pays a small USDC amount on Base for each call: the
server answers an unauthenticated GET with HTTP 402 and payment requirements,
the client signs a micropayment, retries with a payment signature header, and
receives the data. Zerion documents this as an alternative authorization
method for the same endpoints, so this module reuses ``ZerionAPIReader``
unchanged and only swaps the transport. Scout validates the selected
requirements before signing: Base mainnet, the exact USDC contract, an
explicit recipient, a positive timeout, and the configured payment cap.

The observed wallet remains an address-only input. A separate operator-funded
payment wallet signs USDC data fees. Scout installs a hook immediately before
each payment payload is created, including recovery payloads, and reserves the
configured per-payment maximum against one process-lifetime budget.

Enable with ``ZERION_X402_PRIVATE_KEY`` + ``ZERION_WALLET_ADDRESS`` +
``ZERION_X402_PAY_TO``, which pins the only address Scout will pay. Setting
both ``ZERION_API_KEY`` and ``ZERION_X402_PRIVATE_KEY`` is a configuration
error: one authorization mode per source, decided loudly at startup.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import re
import shutil
import signal
import tempfile
from dataclasses import dataclass, field
from decimal import ROUND_FLOOR, Decimal, InvalidOperation
from threading import Lock
from types import FrameType, SimpleNamespace
from typing import Any, Callable, Mapping, Optional, Sequence
from urllib.request import Request

from .hedwig_client import (
    ConsultAnswer,
    HedwigClient,
    HedwigProtocolError,
    HedwigTimeout,
    HedwigUnavailable,
)
from .x402_guard import (
    BASE_NETWORK,
    BASE_USDC_ADDRESS,
    USDC_DECIMALS,
    X402GuardError,
    X402PaymentGuard,
    has_payment_signature,
)
from .zerion_api import (
    API_KEY_ENV,
    CHAIN_ENV,
    WALLET_ENV,
    Transport,
    ZerionAPIAuthError,
    ZerionAPIBudgetError,
    ZerionAPIConfig,
    ZerionAPIError,
    ZerionAPIPaginationError,
    ZerionAPIPaymentError,
    ZerionAPIRateLimitError,
    ZerionAPIReader,
    ZerionAPIServerError,
    ZerionAPITransportError,
    ZerionConfigError,
    ZerionWalletReader,
)

logger = logging.getLogger(__name__)

X402_KEY_ENV = "ZERION_X402_PRIVATE_KEY"
X402_MAX_ENV = "ZERION_X402_MAX_USD_PER_CALL"
X402_SESSION_MAX_ENV = "ZERION_X402_MAX_USD_PER_SESSION"
X402_PAY_TO_ENV = "ZERION_X402_PAY_TO"

#: Path to a built Hedwig stdio MCP server (``node <path>``). Unset means the
#: Hedwig preflight hook is never installed; Scout's own guard and budget
#: still run on their own.
HEDWIG_SERVER_PATH_ENV = "HEDWIG_SERVER_PATH"

#: Default per-payment spend cap. The x402 SDK enforces it before signing.
DEFAULT_MAX_USD_PER_CALL = "$0.05"

# One nominal maximum-page snapshot: one positions request plus 20 transaction pages.
# The budget reserves the per-payment maximum, so this is conservative when
# Zerion charges less than the configured maximum. An SDK recovery payment
# consumes another reservation and may stop the snapshot at this boundary.
DEFAULT_MAX_USD_PER_SESSION = "$1.05"
DEFAULT_MAX_PAYMENTS_PER_SESSION = 21

#: Money strings the x402 SDK accepts and we accept: "$" plus a positive
#: decimal amount. Validated here so a typo is a loud startup error instead
#: of a mid-flight payment failure.
_MONEY_RE = re.compile(r"^\$(0|[1-9][0-9]*)(\.[0-9]+)?$")


def _parse_positive_usd(value: str, *, env_name: str, example: str) -> Decimal:
    if not isinstance(value, str) or not _MONEY_RE.match(value.strip()):
        raise ZerionConfigError(
            f"{env_name} must be a positive USD amount like {example}; got an invalid value"
        )
    try:
        amount = Decimal(value.strip()[1:])
    except InvalidOperation:
        raise ZerionConfigError(f"{env_name} must be a valid USD amount") from None
    if not amount.is_finite() or amount <= 0:
        raise ZerionConfigError(f"{env_name} must be greater than zero")
    return amount


def parse_max_usd_per_call(value: str) -> str:
    """Validate a per-payment USD cap like ``$0.05``; return it unchanged."""
    _parse_positive_usd(value, env_name=X402_MAX_ENV, example=DEFAULT_MAX_USD_PER_CALL)
    return value.strip()


def parse_max_usd_per_session(value: str) -> str:
    """Validate a cumulative process-lifetime USD cap; return it unchanged."""
    _parse_positive_usd(
        value,
        env_name=X402_SESSION_MAX_ENV,
        example=DEFAULT_MAX_USD_PER_SESSION,
    )
    return value.strip()


def _usd(amount: Decimal) -> str:
    return f"${amount:f}"


@dataclass
class X402SpendBudget:
    """Conservative cumulative budget enforced before every x402 signature.

    The SDK does not expose settled cost to this process at payment-creation
    time. Each attempted payment therefore reserves the full per-payment cap.
    Reservations are never refunded after an error because settlement may be
    ambiguous. This favors a smaller usable allowance over silent overspend.
    """

    max_usd_per_call: Decimal
    max_usd_per_session: Decimal
    reserved_usd: Decimal = field(default=Decimal("0"), init=False)
    reserved_payments: int = field(default=0, init=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    @classmethod
    def from_strings(cls, per_call: str, per_session: str) -> "X402SpendBudget":
        call_amount = _parse_positive_usd(
            per_call,
            env_name=X402_MAX_ENV,
            example=DEFAULT_MAX_USD_PER_CALL,
        )
        session_amount = _parse_positive_usd(
            per_session,
            env_name=X402_SESSION_MAX_ENV,
            example=DEFAULT_MAX_USD_PER_SESSION,
        )
        if session_amount < call_amount:
            raise ZerionConfigError(f"{X402_SESSION_MAX_ENV} must be at least {X402_MAX_ENV}")
        return cls(call_amount, session_amount)

    def reserve_payment(self, _context: Any = None) -> None:
        """Reserve one worst-case payment before the SDK creates its payload."""
        with self._lock:
            proposed = self.reserved_usd + self.max_usd_per_call
            if proposed > self.max_usd_per_session:
                raise ZerionAPIBudgetError(
                    "Scout stopped x402 before signing because the session spend "
                    f"budget of {_usd(self.max_usd_per_session)} is exhausted"
                )
            self.reserved_usd = proposed
            self.reserved_payments += 1

    def status(self) -> Mapping[str, Any]:
        """Return safe budget telemetry for host results and reports."""
        with self._lock:
            remaining = self.max_usd_per_session - self.reserved_usd
            return {
                "max_usd_per_payment": _usd(self.max_usd_per_call),
                "max_usd_per_session": _usd(self.max_usd_per_session),
                "reserved_usd": _usd(self.reserved_usd),
                "remaining_usd": _usd(remaining),
                "reserved_payments": self.reserved_payments,
                "accounting": "conservative_max_per_payment",
            }


def hedwig_policy_cap_atomic(max_usd_per_call: str) -> str:
    """Floor a USD cap like ``$0.05`` to atomic USDC units: ``"50000"``.

    Reuses the same validation the ``ZERION_X402_MAX_USD_PER_CALL`` cap gets:
    positive, finite, well-formed, so a negative, zero, non-finite, or
    non-numeric cap is a loud ``ZerionConfigError`` here too, never a
    silently-wrong policy value like ``"-1000000"``. Uses ``ROUND_FLOOR``
    explicitly so a cap with more precision than USDC's 6 decimals is always
    rounded down, never up. A cap that floors to 0 atomic units (for example
    ``$0.0000005``) is rejected too: a policy cap of "0" would silently deny
    every payment, and the operator almost certainly meant a usable cap.
    """
    amount = _parse_positive_usd(
        max_usd_per_call, env_name="the Hedwig policy cap", example=DEFAULT_MAX_USD_PER_CALL
    )
    atomic = int(
        (amount * (Decimal(10) ** USDC_DECIMALS)).to_integral_value(rounding=ROUND_FLOOR)
    )
    if atomic <= 0:
        raise ZerionConfigError(
            f"the Hedwig policy cap must floor to at least 1 atomic USDC unit; "
            f"{max_usd_per_call} floors to {atomic}"
        )
    return str(atomic)


def build_hedwig_policy_document(*, pay_to: str, max_usd_per_call: str) -> Mapping[str, Any]:
    """Build the Hedwig policy Scout derives from its own x402 configuration."""
    return {
        "permits": True,
        "chainId": BASE_NETWORK,
        "approvedRecipients": [pay_to],
        "perActionCaps": {"pay": hedwig_policy_cap_atomic(max_usd_per_call)},
        "role": {"mode": "not-required"},
        # Hedwig v0.3.0 is expected to add this field; a policy written
        # without it would answer UNKNOWN on every call under that release.
        # v0.2.0 ignores unknown policy keys (verified against the real
        # server), so writing it now costs nothing and keeps Scout working
        # across the upgrade without a code change on this side.
        "authorizationWindow": {"mode": "not-required"},
    }


def write_hedwig_policy_file(*, pay_to: str, max_usd_per_call: str) -> tuple[str, str]:
    """Write a 0600 Hedwig policy file into a fresh ``mkdtemp`` directory.

    The document is built, and its cap validated, before ``mkdtemp`` runs: an
    invalid cap raises before any directory or file exists, instead of
    leaking an empty temp dir for every rejected value.

    Returns ``(policy_path, policy_dir)``. The caller owns removing
    ``policy_dir``; ``build_hedwig_client`` registers that cleanup to run at
    process exit and on SIGTERM.
    """
    document = build_hedwig_policy_document(pay_to=pay_to, max_usd_per_call=max_usd_per_call)
    policy_dir = tempfile.mkdtemp(prefix="scout-hedwig-")
    policy_path = os.path.join(policy_dir, "policy.json")
    fd = os.open(policy_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(document, handle)
    return policy_path, policy_dir


def _force_close_no_lock(client: HedwigClient, policy_dir: str) -> None:
    """Tear down the child and the policy dir without the client's lock.

    Safe to call from a SIGTERM handler even while the main thread is
    stopped mid-call, holding the lock inside ``consult_payment``: a plain
    ``threading.Lock`` is not reentrant, so a handler that called
    ``client.close()`` (which acquires that same lock) would deadlock the
    interrupted thread against itself. This touches the raw subprocess
    directly instead; the blocked read already treats a dead pipe (EOF) as
    a protocol error, so the interrupted call still unwinds cleanly once the
    child is gone, with no lock involved on this side at all.
    """
    process = client._process
    if process is not None:
        try:
            process.terminate()
        except OSError:
            pass
        try:
            process.wait(timeout=0.5)
        except Exception:
            try:
                process.kill()
            except OSError:
                pass
            try:
                process.wait(timeout=0.5)
            except Exception:
                pass
    client._unavailable = True
    shutil.rmtree(policy_dir, ignore_errors=True)


def _install_process_exit_cleanup(cleanup: Callable[[], None]) -> None:
    """Run ``cleanup`` at normal process exit and, best-effort, on SIGTERM.

    ``atexit`` alone never fires on SIGTERM (Python exits with status -15
    without unwinding), which would leave the policy dir and the Hedwig
    child behind. The SIGTERM handler chains to whatever handler was already
    installed (if any) after cleanup runs, so a second installation in the
    same process composes instead of silently replacing the first.
    ``cleanup`` itself must never block on anything the interrupted thread
    might already hold; see ``_force_close_no_lock``.
    """
    atexit.register(cleanup)
    try:
        previous_handler = signal.getsignal(signal.SIGTERM)
    except ValueError:
        return  # not the main thread; atexit above still covers a normal exit

    def _on_sigterm(signum: int, frame: Optional[FrameType]) -> None:
        cleanup()
        signal.signal(signal.SIGTERM, previous_handler)
        if callable(previous_handler):
            previous_handler(signum, frame)
        else:
            os.kill(os.getpid(), signum)

    try:
        signal.signal(signal.SIGTERM, _on_sigterm)
    except ValueError:
        pass  # not the main thread; atexit above still covers a normal exit


#: A version-handshake result row carrying a code with this suffix means
#: Hedwig's policy schema and Scout's generated policy are out of step (for
#: example, a future Hedwig release requiring a field this policy lacks).
_HANDSHAKE_REJECT_SUFFIXES = ("_POLICY_MISSING", "_POLICY_MALFORMED")


def _handshake_rejection_reason(answer: ConsultAnswer) -> Optional[str]:
    code = answer.worst_row_code or ""
    if any(code.endswith(suffix) for suffix in _HANDSHAKE_REJECT_SUFFIXES):
        return f"the policy check returned {code}"
    if not answer.proceed:
        return (
            f"the fixture consult did not proceed "
            f"(verdict={answer.verdict}, code={code or 'none'})"
        )
    return None


def build_hedwig_client(
    environ: Mapping[str, str],
    *,
    pay_to: Optional[str],
    max_usd_per_call: str,
    command: Optional[Sequence[str]] = None,
    spawn_deadline: Optional[float] = None,
    call_deadline: Optional[float] = None,
) -> Optional[HedwigClient]:
    """Build Scout's Hedwig second-opinion client, or ``None`` when it is not installed.

    Only active when ``HEDWIG_SERVER_PATH`` is set and a recipient pin
    exists: an unset path means the hook is never installed at all, and a
    missing pin means there is nothing valid to put in Hedwig's policy.
    ``command`` overrides the spawned argv (tests inject the fake server);
    production leaves it unset and gets ``["node", server_path]``.

    Before returning, this runs ONE fixture ``consult`` against Hedwig, built
    from the same policy just written, as a version handshake: a policy
    schema mismatch (Hedwig answering UNKNOWN with a `*_POLICY_MISSING` or
    `*_POLICY_MALFORMED` code, or any non-proceeding answer) surfaces here,
    at startup, where an operator can fix it, instead of on the first real
    payment. A handshake failure tears down what was just spawned and raises
    ``ZerionConfigError`` with code ``hedwig_policy_rejected``.
    """
    server_path = (environ.get(HEDWIG_SERVER_PATH_ENV) or "").strip()
    if not server_path or not pay_to:
        return None
    policy_path, policy_dir = write_hedwig_policy_file(
        pay_to=pay_to, max_usd_per_call=max_usd_per_call
    )
    client_kwargs: dict[str, Any] = {}
    if spawn_deadline is not None:
        client_kwargs["spawn_deadline"] = spawn_deadline
    if call_deadline is not None:
        client_kwargs["call_deadline"] = call_deadline
    client = HedwigClient(
        list(command) if command is not None else ["node", server_path],
        policy_file=policy_path,
        environ=environ,
        **client_kwargs,
    )

    def _cleanup() -> None:
        _force_close_no_lock(client, policy_dir)

    _install_process_exit_cleanup(_cleanup)

    fixture_requirements = SimpleNamespace(
        network=BASE_NETWORK,
        asset=BASE_USDC_ADDRESS,
        pay_to=pay_to,
        get_amount=lambda: hedwig_policy_cap_atomic(max_usd_per_call),
    )
    try:
        handshake = client.consult_payment(fixture_requirements)
    except (HedwigTimeout, HedwigProtocolError, HedwigUnavailable) as exc:
        _cleanup()
        raise ZerionConfigError(
            f"Scout refused to start x402 with Hedwig (hedwig_policy_rejected): "
            f"the version handshake with Hedwig failed: {exc}"
        ) from None
    rejection = _handshake_rejection_reason(handshake)
    if rejection is not None:
        _cleanup()
        raise ZerionConfigError(
            f"Scout refused to start x402 with Hedwig (hedwig_policy_rejected): {rejection}"
        )
    return client


def build_payment_session(
    private_key: str,
    max_usd_per_call: str = DEFAULT_MAX_USD_PER_CALL,
    *,
    spend_budget: Optional[X402SpendBudget] = None,
    pay_to: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> Any:
    """Build a requests Session that settles x402 payments automatically.

    Lazy-imports the optional ``x402`` SDK so the default install stays
    dependency-free. The returned SDK session retains signing authority for
    its lifetime. Scout does not log the key or include it in returned errors.
    """
    try:
        from eth_account import Account
        from x402 import x402ClientSync
        from x402.http.clients import x402_requests
        from x402.mechanisms.evm import EthAccountSigner
        from x402.mechanisms.evm.exact.register import register_exact_evm_client
    except ImportError as exc:
        raise ZerionConfigError(
            "x402 mode requires the optional dependency group: pip install -e '.[x402]'"
        ) from exc
    try:
        account = Account.from_key(private_key)
    except Exception:
        # Never echo the exception text: it may contain the key material.
        raise ZerionConfigError(f"{X402_KEY_ENV} is not a valid EVM private key") from None
    client = x402ClientSync()
    # EthAccountSigner is load-bearing for the spend cap, not just a default.
    # The SDK's gas-sponsoring extension signs approve(Permit2, MaxUint256), an
    # unlimited USDC allowance that no cap or recipient pin bounds. It is gated
    # on isinstance(signer, ClientEvmSignerWithSignTransaction), which this
    # signer is not. Swapping in EthAccountSignerWithRPC re-opens that path.
    register_exact_evm_client(client, EthAccountSigner(account), networks=BASE_NETWORK)
    client.set_spend_controls({"max_amount_per_payment": max_usd_per_call})
    guard = X402PaymentGuard.from_usd(max_usd_per_call, pay_to=pay_to)
    hedwig_client = build_hedwig_client(
        environ if environ is not None else os.environ,
        pay_to=pay_to,
        max_usd_per_call=max_usd_per_call,
    )
    client.on_before_payment_creation(
        lambda context: preflight_before_signing(
            context,
            guard=guard,
            spend_budget=spend_budget,
            hedwig_client=hedwig_client,
        )
    )
    return x402_requests(client)


def preflight_before_signing(
    context: Any,
    *,
    guard: X402PaymentGuard,
    spend_budget: Optional[X402SpendBudget] = None,
    hedwig_client: Optional[HedwigClient] = None,
) -> None:
    """Validate the selected payment before reserving budget or signing.

    The x402 SDK invokes this callback after it has parsed a 402 response and
    immediately before it creates a payment payload. Requirement validation is
    intentionally before budget reservation: an unsupported chain, asset,
    recipient or amount must not burn Scout's allowance. Hedwig's second
    opinion, when installed, runs after Scout's own guard and before the same
    reservation, for the same reason: a denial must not burn Scout's
    allowance either.
    """
    try:
        guard.validate(context)
    except X402GuardError as exc:
        raise ZerionAPIPaymentError(
            f"Scout refused x402 payment before signing ({exc.code})", status=402
        ) from None
    if hedwig_client is not None:
        _consult_hedwig(context, hedwig_client)
    if spend_budget is not None:
        spend_budget.reserve_payment()


def _selected_requirements(context: Any) -> Any:
    if isinstance(context, Mapping):
        return context.get("selected_requirements")
    return getattr(context, "selected_requirements", None)


def _consult_hedwig(context: Any, hedwig_client: HedwigClient) -> None:
    """Ask Hedwig's second opinion; fail closed on any of its three exceptions."""
    requirements = _selected_requirements(context)
    try:
        answer = hedwig_client.consult_payment(requirements)
    except (HedwigTimeout, HedwigProtocolError, HedwigUnavailable):
        raise ZerionAPIPaymentError(
            "Scout refused x402 payment before signing (hedwig_unavailable)", status=402
        ) from None
    if answer.proceed:
        return
    # Evidence is detailed enough to carry a caller-shaped string (Hedwig's
    # own evidence text); it goes to Scout's own debug log, not the raised
    # error, so the error surface stays a bounded, predictable shape.
    logger.debug(
        "hedwig consult: verdict=%s worst_row_id=%s worst_row_code=%s worst_row_evidence=%s",
        answer.verdict,
        answer.worst_row_id,
        answer.worst_row_code,
        answer.worst_row_evidence,
    )
    code = "hedwig_deny" if answer.verdict == "DENY" else "hedwig_unknown"
    raise ZerionAPIPaymentError(
        f"Scout refused x402 payment before signing ({code}): "
        f"worst row {answer.worst_row_id} ({answer.worst_row_code})",
        status=402,
    )


def _is_x402_payment_error(exc: Exception) -> bool:
    """Identify SDK payment-flow failures without requiring x402 by default."""
    try:
        from x402.http.clients.requests import PaymentError
    except ImportError:
        return False
    return isinstance(exc, PaymentError)


def _contains_budget_error(exc: BaseException) -> bool:
    """Find Scout's typed budget stop through SDK exception wrapping."""
    seen: set[int] = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        if isinstance(current, ZerionAPIBudgetError):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def x402_transport(session: Any) -> Transport:
    """Adapt an x402-wrapped requests Session to the reader's transport slot.

    Mirrors ``ZerionAPIReader._request``'s typed-error contract so the host's
    observe boundary reports x402 failures with the same error kinds. A 402
    that reaches this layer means the SDK could not complete the paid request.
    Scout adds no retry loop around that result.
    """

    def transport(request: Request, timeout: float) -> Mapping[str, Any]:
        try:
            response = session.get(
                request.full_url,
                headers=dict(request.header_items()),
                timeout=timeout,
            )
        except Exception as exc:
            if _contains_budget_error(exc):
                raise ZerionAPIBudgetError(
                    "Scout stopped x402 before signing because the session spend "
                    "budget is exhausted"
                ) from None
            if _is_x402_payment_error(exc):
                # A signed request may already have reached the facilitator.
                # Require inspection before another attempt. The raw SDK error
                # can contain provider or signer detail, so do not chain it.
                raise ZerionAPIPaymentError(
                    "Zerion x402 payment could not be prepared or settled; "
                    "inspect payment state before retrying",
                    status=402,
                ) from None
            raise ZerionAPITransportError("Zerion API x402 transport failed") from None
        response_request = getattr(response, "request", None)
        response_request_headers = getattr(response_request, "headers", None)
        if _is_paid_retry(response_request_headers) and not has_payment_signature(
            response_request_headers
        ):
            raise ZerionAPIPaymentError(
                "Zerion x402 retry was missing the PAYMENT-SIGNATURE header; "
                "Scout will not accept the response",
                status=402,
            )
        status = getattr(response, "status_code", None)
        if status == 200:
            try:
                payload = json.loads(response.content)
            except (TypeError, ValueError, AttributeError):
                raise ZerionAPITransportError(
                    "Zerion API returned an undecodable response"
                ) from None
            if not isinstance(payload, Mapping):
                raise ZerionAPITransportError("Zerion API returned a non-object JSON response")
            return payload
        headers = getattr(response, "headers", None)
        if status in (401, 403):
            raise ZerionAPIAuthError("Zerion API authorization failed", status=status)
        if status == 402:
            raise ZerionAPIPaymentError(
                "Zerion API rejected the x402 payment; check the payment wallet's "
                "USDC balance on Base and the spend cap",
                status=402,
            )
        if status == 404:
            raise ZerionAPIError("Zerion API returned HTTP 404", status=404)
        if status == 429:
            raise ZerionAPIRateLimitError(
                "Zerion API rate limit reached",
                status=429,
                retry_after_seconds=ZerionAPIReader._parse_retry_after(headers),
            )
        if isinstance(status, int) and 500 <= status < 600:
            raise ZerionAPIServerError(
                "Zerion API reported a server error",
                status=status,
                retry_after_seconds=ZerionAPIReader._parse_retry_after(headers),
            )
        if not isinstance(status, int):
            raise ZerionAPITransportError("Zerion API returned a response without HTTP status")
        raise ZerionAPIError(f"Zerion API returned HTTP {status}", status=status)

    return transport


def _is_paid_retry(headers: Any) -> bool:
    """Identify the x402 adapter's signed retry, not the first unpaid GET."""

    if not isinstance(headers, Mapping):
        return False
    return any(
        str(name).lower() in {"payment-retry", "payment-recovery"} and str(value) == "1"
        for name, value in headers.items()
    )


def reader_from_env(
    environ: Mapping[str, str], *, session: Any = None
) -> Optional[ZerionWalletReader]:
    """Build the x402-backed Zerion source, or None when x402 is not enabled.

    Gating mirrors the API-key source: returns None only when
    ``ZERION_X402_PRIVATE_KEY`` is absent, raises ZerionConfigError on any
    partial or conflicting configuration, and never falls back to the fixture.
    ``session`` is injectable for tests; production callers leave it None and
    get a real SDK-backed payment session.
    """
    x402_key = (environ.get(X402_KEY_ENV) or "").strip()
    if not x402_key:
        return None
    api_key = (environ.get(API_KEY_ENV) or "").strip()
    if api_key:
        raise ZerionConfigError(
            f"Set either {API_KEY_ENV} or {X402_KEY_ENV}, not both: the Zerion "
            "source uses exactly one authorization mode."
        )
    wallet = (environ.get(WALLET_ENV) or "").strip()
    if not wallet:
        raise ZerionConfigError(
            f"{X402_KEY_ENV} and {WALLET_ENV} must both be set to enable the "
            f"x402 Zerion source; {WALLET_ENV} is missing. The fixture is not "
            "used as a fallback."
        )
    pay_to = (environ.get(X402_PAY_TO_ENV) or "").strip()
    if not pay_to:
        # Gated at startup, not in the guard. Only here can Scout tell "the
        # operator never configured a recipient" from "the server named the
        # wrong one"; the second is a 402 mid-run and reads like an endpoint
        # fault. Unset used to mean "pay whoever the server names", which is an
        # attacker-chosen address as correct behavior.
        raise ZerionConfigError(
            f"{X402_KEY_ENV} and {X402_PAY_TO_ENV} must both be set to enable "
            f"the x402 Zerion source; {X402_PAY_TO_ENV} is missing. It pins the "
            "only address Scout may pay."
        )
    max_usd = parse_max_usd_per_call(
        (environ.get(X402_MAX_ENV) or "").strip() or DEFAULT_MAX_USD_PER_CALL
    )
    configured_session_max = (environ.get(X402_SESSION_MAX_ENV) or "").strip()
    if configured_session_max:
        max_session_usd = parse_max_usd_per_session(configured_session_max)
    else:
        max_session_usd = _usd(
            _parse_positive_usd(
                max_usd,
                env_name=X402_MAX_ENV,
                example=DEFAULT_MAX_USD_PER_CALL,
            )
            * DEFAULT_MAX_PAYMENTS_PER_SESSION
        )
    budget = X402SpendBudget.from_strings(max_usd, max_session_usd)
    chain = (environ.get(CHAIN_ENV) or "").strip() or "multi-chain"
    if session is None:
        # HEDWIG_SERVER_PATH is deliberately not threaded from this reader's
        # own `environ` mapping: it is an ambient process setting Scout reads
        # from the real environment (build_payment_session's own default),
        # the same way any other MCP server host config would be, not part
        # of this source's own x402 configuration bundle.
        session = build_payment_session(x402_key, max_usd, spend_budget=budget, pay_to=pay_to)
    # api_key=None: the reader sends no Authorization header; the transport
    # settles access per request via x402 instead.
    api_reader = ZerionAPIReader(ZerionAPIConfig(api_key=None), transport=x402_transport(session))
    return ZerionWalletReader(api_reader, wallet, chain, spend_budget=budget)


# Re-exported so callers can catch pagination errors from this module's
# reader without importing zerion_api separately.
__all__ = [
    "API_KEY_ENV",
    "CHAIN_ENV",
    "DEFAULT_MAX_USD_PER_CALL",
    "DEFAULT_MAX_USD_PER_SESSION",
    "DEFAULT_MAX_PAYMENTS_PER_SESSION",
    "HEDWIG_SERVER_PATH_ENV",
    "WALLET_ENV",
    "X402_KEY_ENV",
    "X402_MAX_ENV",
    "X402_SESSION_MAX_ENV",
    "X402SpendBudget",
    "ZerionAPIPaginationError",
    "ZerionConfigError",
    "build_hedwig_client",
    "build_hedwig_policy_document",
    "build_payment_session",
    "hedwig_policy_cap_atomic",
    "parse_max_usd_per_call",
    "parse_max_usd_per_session",
    "preflight_before_signing",
    "reader_from_env",
    "write_hedwig_policy_file",
    "x402_transport",
]
