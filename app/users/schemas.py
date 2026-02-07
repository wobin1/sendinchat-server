from pydantic import BaseModel, Field
from typing import Optional


class UserCreate(BaseModel):
    """Schema for creating a new user."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class UserOut(BaseModel):
    """Schema for user output (without password)."""
    id: int
    username: str
    is_active: bool
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for token payload data."""
    username: Optional[str] = None


class UserResponse(BaseModel):
    """Standard response for user operations."""
    status: str
    message: str
    data: Optional[UserOut] = None


class TokenResponse(BaseModel):
    """Standard response for token operations."""
    status: str
    message: str
    data: Optional[Token] = None
