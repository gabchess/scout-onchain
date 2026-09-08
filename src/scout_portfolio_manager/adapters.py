"""Test-only fake execution adapter.

Not part of the host or MCP public API. Do not import from package consumers.
Kept for isolated domain tests.
"""

from datetime import datetime, timezone
from typing import Dict, Optional, Set

from .safety import DcaPreview

FAILURE_CODES = frozenset({"authorization_rejected", "timeout", "settlement_mismatch"})


class ExecutionError(RuntimeError):
    pass


class ExecutionResult:
    def __init__(self, execution_id: str, status: str):
        self.execution_id = execution_id
        self.status = status


class FakeExecutionAdapter:
    def __init__(
        self,
        *,
        balance_usd: float = 1000,
        allowed_destinations=None,
        supported_chains=None,
        failure: Optional[str] = None,
    ):
        if failure is not None and failure not in FAILURE_CODES:
            raise ValueError("unsupported failure code: %s" % failure)
        self.balance_usd = balance_usd
        self.allowed_destinations: Set[str] = set(allowed_destinations or {"wallet:0xdef456"})
        self.supported_chains: Set[str] = set(supported_chains or {"ethereum"})
        self.failure = failure
        self._seen: Dict[str, ExecutionResult] = {}
        self._next_id = 1

    def execute(
        self, preview: DcaPreview, *, approval: bool, idempotency_key: str
    ) -> ExecutionResult:
        if not approval:
            raise ExecutionError("explicit approval is required")
        if self.failure:
            raise ExecutionError(self.failure)
        if preview.chain not in self.supported_chains:
            raise ExecutionError("unsupported chain")
        if preview.quote_expiry <= datetime.now(timezone.utc):
            raise ExecutionError("stale quote")
        if idempotency_key in self._seen:
            raise ExecutionError("duplicate request")
        if preview.amount_usd > self.balance_usd:
            raise ExecutionError("insufficient balance")
        if preview.destination not in self.allowed_destinations:
            raise ExecutionError("wrong destination")
        result = ExecutionResult("fake-tx-%d" % self._next_id, "submitted")
        self._next_id += 1
        self._seen[idempotency_key] = result
        return result
