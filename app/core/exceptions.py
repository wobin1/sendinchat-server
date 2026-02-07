from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Union


class APIException(Exception):
    """Custom API exception that returns standardized error responses."""
    
    def __init__(
        self,
        status_code: int,
        message: str,
        data: Union[dict, None] = None
    ):
        self.status_code = status_code
        self.message = message
        self.data = data
        super().__init__(message)


async def api_exception_handler(request: Request, exc: APIException):
    """Handler for custom API exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.message,
            "data": exc.data
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handler for request validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Validation error",
            "data": {"errors": exc.errors()}
        }
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """Handler for unhandled exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "Internal server error",
            "data": None
        }
    )
