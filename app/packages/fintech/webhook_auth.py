import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import settings

security = HTTPBasic()


def webhook_ack_response() -> dict:
    """Return the provider-required webhook acknowledgement payload."""
    return {
        "success": True,
        "status": "success",
        "code": "00",
        "message": "Acknowledged",
    }


def verify_webhook_basic_auth(
    credentials: HTTPBasicCredentials = Depends(security),
) -> str:
    """Validate HTTP Basic Auth credentials for incoming wallet webhooks."""
    if not settings.WEBHOOK_USERNAME or not settings.WEBHOOK_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook authentication is not configured",
        )

    username_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        settings.WEBHOOK_USERNAME.encode("utf-8"),
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        settings.WEBHOOK_PASSWORD.encode("utf-8"),
    )
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
