"""Fail-closed checks immediately before Scout creates an x402 payment."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

BASE_NETWORK = "eip155:8453"
BASE_USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
PAYMENT_SIGNATURE_HEADER = "PAYMENT-SIGNATURE"
USDC_DECIMALS = 6


class X402GuardError(ValueError):
    """A payment requirement failed before signing."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class X402PaymentGuard:
    """Validate the exact Base/USDC data-fee contract Scout currently supports."""

    max_usd_per_payment: Decimal
    network: str = BASE_NETWORK
    asset: str = BASE_USDC_ADDRESS

    @classmethod
    def from_usd(cls, value: str) -> "X402PaymentGuard":
        try:
            amount = Decimal(value.strip().lstrip("$"))
        except (AttributeError, InvalidOperation):
            raise X402GuardError("payment_cap_invalid", "x402 payment cap is invalid") from None
        if not amount.is_finite() or amount <= 0:
            raise X402GuardError("payment_cap_invalid", "x402 payment cap must be positive")
        return cls(amount)

    def validate(self, context: Any) -> None:
        """Validate SDK-selected requirements before a signer sees them."""

        requirements = _value(context, "selected_requirements")
        if requirements is None:
            raise X402GuardError(
                "payment_requirements_missing",
                "Scout refused x402 because selected payment requirements were missing",
            )

        if _value(requirements, "network") != self.network:
            raise X402GuardError(
                "chain_not_allowed",
                "Scout only permits x402 payment requirements on Base mainnet",
            )
        if _value(requirements, "scheme") != "exact":
            raise X402GuardError(
                "scheme_not_allowed",
                "Scout only permits the exact x402 payment scheme",
            )

        asset = _value(requirements, "asset")
        if not isinstance(asset, str) or asset.lower() != self.asset.lower():
            raise X402GuardError(
                "asset_not_allowed",
                "Scout only permits the configured Base USDC contract",
            )

        amount = _value(requirements, "amount")
        if not isinstance(amount, str) or not amount.isdecimal() or not amount.isascii():
            raise X402GuardError(
                "amount_invalid",
                "Scout requires a positive integer USDC amount in atomic units",
            )
        atomic_amount = int(amount)
        if atomic_amount <= 0:
            raise X402GuardError("amount_invalid", "Scout requires a positive payment amount")
        usd_amount = Decimal(atomic_amount) / (Decimal(10) ** USDC_DECIMALS)
        if usd_amount > self.max_usd_per_payment:
            raise X402GuardError(
                "payment_cap_exceeded",
                "Scout refused an x402 amount above its configured per-payment cap",
            )

        pay_to = _value(requirements, "pay_to")
        if not isinstance(pay_to, str) or not pay_to.strip():
            raise X402GuardError("pay_to_missing", "Scout requires an explicit x402 recipient")

        timeout = _value(requirements, "max_timeout_seconds")
        if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
            raise X402GuardError(
                "timeout_invalid",
                "Scout requires an explicit positive x402 timeout",
            )


def has_payment_signature(headers: Mapping[str, Any] | None) -> bool:
    """Return whether headers contain a non-empty PAYMENT-SIGNATURE value."""

    if headers is None:
        return False
    for name, value in headers.items():
        if str(name).lower() == PAYMENT_SIGNATURE_HEADER.lower():
            return isinstance(value, str) and bool(value.strip())
    return False


def _value(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


__all__ = [
    "BASE_NETWORK",
    "BASE_USDC_ADDRESS",
    "PAYMENT_SIGNATURE_HEADER",
    "X402GuardError",
    "X402PaymentGuard",
    "has_payment_signature",
]
