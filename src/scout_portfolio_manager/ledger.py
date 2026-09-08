from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from .contracts import BasisInput, Transaction


class TransactionLedger:
    def __init__(self) -> None:
        self._transactions: List[Transaction] = []
        self._basis: Dict[str, BasisInput] = {}

    def add(
        self,
        tx_id: str,
        *,
        kind: Literal["buy", "sell", "transfer", "fee"],
        asset: str,
        quantity: float,
        value_usd: float,
        fee_usd: float = 0,
    ) -> Transaction:
        tx = Transaction(
            id=tx_id,
            kind=kind,
            asset=asset,
            quantity=quantity,
            value_usd=value_usd,
            fee_usd=fee_usd,
            occurred_at=datetime.now(timezone.utc),
            wallet_address="ledger-local",
        )
        self._transactions.append(tx)
        return tx

    def add_basis(
        self,
        *,
        asset: str,
        amount_usd: float,
        source: Literal["observed_transactions", "user_input"],
        as_of: Optional[datetime] = None,
    ) -> BasisInput:
        basis = BasisInput(asset=asset, amount_usd=amount_usd, source=source, as_of=as_of)
        self._basis[asset] = basis
        return basis

    def transactions(self) -> List[Transaction]:
        return list(self._transactions)

    def basis(self, asset: str) -> Optional[BasisInput]:
        return self._basis.get(asset)
