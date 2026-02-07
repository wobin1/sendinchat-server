from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel


DataT = TypeVar('DataT')


class APIResponse(BaseModel, Generic[DataT]):
    """Standard API response structure."""
    status: str
    message: str
    data: Optional[DataT] = None

    class Config:
        from_attributes = True


def success_response(data: Any = None, message: str = "Success") -> dict:
    """Create a success response."""
    return {
        "status": "success",
        "message": message,
        "data": data
    }


def error_response(message: str, data: Any = None) -> dict:
    """Create an error response."""
    return {
        "status": "error",
        "message": message,
        "data": data
    }
