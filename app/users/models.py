from typing import Optional
from datetime import datetime


class User:
    """User model for authentication and user management."""
    
    def __init__(
        self,
        id: int,
        username: str,
        hashed_password: str,
        wallet_account: Optional[str] = None,
        is_active: bool = True,
        created_at: Optional[datetime] = None
    ):
        self.id = id
        self.username = username
        self.hashed_password = hashed_password
        self.wallet_account = wallet_account
        self.is_active = is_active
        self.created_at = created_at
    
    @classmethod
    def from_record(cls, record) -> "User":
        """Create User instance from database record."""
        return cls(
            id=record["id"],
            username=record["username"],
            hashed_password=record["hashed_password"],
            wallet_account=record.get("wallet_account"),
            is_active=record["is_active"],
            created_at=record.get("created_at")
        )
