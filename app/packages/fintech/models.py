from typing import Optional
from decimal import Decimal
from datetime import datetime


class Transaction:
    """Transaction model for P2P fund transfers."""
    
    def __init__(
        self,
        id: int,
        sender_id: int,
        receiver_id: int,
        amount: Decimal,
        status: str = "pending",
        created_at: Optional[datetime] = None
    ):
        self.id = id
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.amount = amount
        self.status = status
        self.created_at = created_at
    
    @classmethod
    def from_record(cls, record) -> "Transaction":
        """Create Transaction instance from database record."""
        return cls(
            id=record["id"],
            sender_id=record["sender_id"],
            receiver_id=record["receiver_id"],
            amount=record["amount"],
            status=record["status"],
            created_at=record.get("created_at")
        )
