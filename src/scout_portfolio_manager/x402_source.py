"""Optional x402 pay-per-call source for the read-only Zerion adapter.

x402 (https://x402.org) is an open pay-per-request HTTP protocol. Instead of
an API key, the client pays a small USDC amount on Base for each call: the
server answers an unauthenticated GET with HTTP 402 and payment requirements,
the client signs a micropayment, retries with a payment signature header, and
receives the data. Zerion documents this as an alternative authorization
method for the same endpoints, so this module reuses ``ZerionAPIReader``
unchanged and only swaps the transport.

The observed wallet remains an address-only input. A separate operator-funded
payment wallet signs USDC data fees. The x402 SDK enforces a per-payment cap;
Scout has no cumulative spend budget.

Enable with ``ZERION_X402_PRIVATE_KEY`` + ``ZERION_WALLET_ADDRESS``. Setting
both ``ZERION_API_KEY`` and ``ZERION_X402_PRIVATE_KEY`` is a configuration
error: one authorization mode per source, decided loudly at startup.
"""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Optional
from urllib.request import Request

from .zerion_api import (
    API_KEY_ENV,
    CHAIN_ENV,
    WALLET_ENV,
    Transport,
    ZerionAPIAuthError,
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

#: Default per-payment spend cap. The x402 SDK enforces it before signing.
DEFAULT_MAX_USD_PER_CALL = "$0.05"

#: Money strings the x402 SDK accepts and we accept: "$" plus a positive
#: decimal amount. Validated here so a typo is a loud startup error instead
#: of a mid-flight payment failure.
_MONEY_RE = re.compile(r"^\$(0|[1-9][0-9]*)(\.[0-9]+)?$")


def parse_max_usd_per_call(value: str) -> str:
    """Validate a per-payment USD cap like ``$0.05``; return it unchanged.

    Raises ZerionConfigError on anything that is not a positive USD money
    string, so the spend cap can never silently degrade to "no cap".
    """
    if not isinstance(value, str) or not _MONEY_RE.match(value.strip()):
        raise ZerionConfigError(
            f"{X402_MAX_ENV} must be a positive USD amount like "
            f"{DEFAULT_MAX_USD_PER_CALL}; got an invalid value"
        )
    try:
        amount = Decimal(value.strip()[1:])
    except InvalidOperation:
        raise ZerionConfigError(f"{X402_MAX_ENV} must be a valid USD amount") from None
    if not amount.is_finite() or amount <= 0:
        raise ZerionConfigError(f"{X402_MAX_ENV} must be greater than zero")
    return value.strip()


def build_payment_session(
    private_key: str, max_usd_per_call: str = DEFAULT_MAX_USD_PER_CALL
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
            "x402 mode requires the optional dependency group: "
            "pip install -e '.[x402]'"
        ) from exc
    try:
        account = Account.from_key(private_key)
    except Exception:
        # Never echo the exception text: it may contain the key material.
        raise ZerionConfigError(f"{X402_KEY_ENV} is not a valid EVM private key") from None
    client = x402ClientSync()
    register_exact_evm_client(client, EthAccountSigner(account))
    client.set_spend_controls({"max_amount_per_payment": max_usd_per_call})
    return x402_requests(client)


def _is_x402_payment_error(exc: Exception) -> bool:
    """Identify SDK payment-flow failures without requiring x402 by default."""
    try:
        from x402.http.clients.requests import PaymentError
    except ImportError:
        return False
    return isinstance(exc, PaymentError)


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
            if _is_x402_payment_error(exc):
                # A signed request may already have reached the facilitator.
                # Require inspection before another attempt. The raw SDK error
                # can contain provider or signer detail, so do not chain it.
                raise ZerionAPIPaymentError(
                    "Zerion x402 payment could not be prepared or settled; "
                    "inspect payment state before retrying",
                    status=402,
                ) from None
            raise ZerionAPITransportError("Zerion API x402 transport failed") from exc
        status = getattr(response, "status_code", None)
        if status == 200:
            try:
                payload = json.loads(response.content)
            except (TypeError, ValueError, AttributeError) as exc:
                raise ZerionAPITransportError(
                    "Zerion API returned an undecodable response"
                ) from exc
            if not isinstance(payload, Mapping):
                raise ZerionAPITransportError(
                    "Zerion API returned a non-object JSON response"
                )
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
    max_usd = parse_max_usd_per_call(
        (environ.get(X402_MAX_ENV) or "").strip() or DEFAULT_MAX_USD_PER_CALL
    )
    chain = (environ.get(CHAIN_ENV) or "").strip() or "multi-chain"
    if session is None:
        session = build_payment_session(x402_key, max_usd)
    # api_key=None: the reader sends no Authorization header; the transport
    # settles access per request via x402 instead.
    api_reader = ZerionAPIReader(
        ZerionAPIConfig(api_key=None), transport=x402_transport(session)
    )
    return ZerionWalletReader(api_reader, wallet, chain)


# Re-exported so callers can catch pagination errors from this module's
# reader without importing zerion_api separately.
__all__ = [
    "API_KEY_ENV",
    "CHAIN_ENV",
    "DEFAULT_MAX_USD_PER_CALL",
    "WALLET_ENV",
    "X402_KEY_ENV",
    "X402_MAX_ENV",
    "ZerionAPIPaginationError",
    "ZerionConfigError",
    "build_payment_session",
    "parse_max_usd_per_call",
    "reader_from_env",
    "x402_transport",
]
