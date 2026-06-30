from datetime import datetime
import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError

from app.packages.fintech import service as fintech_service
from app.packages.fintech.schemas import (
    InflowWebhookPayload,
    ProviderWebhookAckResponse,
    UpgradeStatusWebhookPayload,
)
from app.packages.fintech.service import JsonDatabase
from app.packages.fintech.webhook_auth import verify_webhook_basic_auth, webhook_ack_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fintech/webhooks", tags=["fintech-webhooks"])


def _classify_event(payload: Dict[str, Any]) -> str:
    """Best-effort classification for a wallet-provider callback payload."""
    for key in ("eventType", "notificationType", "transactionType", "type", "event", "status"):
        value = payload.get(key)
        if value is None:
            continue
        normalized = str(value).strip().lower()
        if "upgrade" in normalized:
            return "upgrade-status"
        if any(token in normalized for token in ("inflow", "credit", "incoming")):
            return "inflow"
    if payload.get("upgradeStatus"):
        return "upgrade-status"
    if payload.get("accountNumber") and payload.get("transactionReference"):
        return "inflow"
    return "raw"


def _record_webhook(payload: Dict[str, Any], event_type: str) -> Dict[str, Any]:
    """Persist the webhook payload for later inspection or manual replay."""
    db = JsonDatabase.read()
    record = {
        "id": payload.get("transactionReference")
        or payload.get("reference")
        or f"wallet-webhook-{datetime.utcnow().timestamp()}",
        "source": "wallet-provider",
        "eventType": event_type,
        "payload": payload,
        "receivedAt": datetime.utcnow().isoformat() + "Z",
        "processed": False,
    }
    db.setdefault("webhookEvents", []).append(record)
    JsonDatabase.write(db)
    return record


async def _extract_payload(request: Request) -> Dict[str, Any]:
    """
    Read the webhook body from JSON, form data, or query params.

    JSON is preferred. Empty bodies are treated as an empty object so Swagger
    tests do not fail, and query params are used as a last fallback.
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type or not content_type:
        body = await request.body()
        if not body or not body.strip():
            return {}
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "status": "error", "code": "01", "message": "Webhook body must be valid JSON"},
            )
        if not isinstance(parsed, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"success": False, "status": "error", "code": "01", "message": "Webhook payload must be a JSON object"},
            )
        return parsed

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        return dict(form)

    if request.query_params:
        return dict(request.query_params)

    body = await request.body()
    if not body or not body.strip():
        return {}

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "status": "error", "code": "01", "message": "Webhook body must be valid JSON"},
        )
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "status": "error", "code": "01", "message": "Webhook payload must be a JSON object"},
        )
    return parsed


def _process_webhook_payload(payload: Dict[str, Any], event_type: str) -> None:
    """Route a classified webhook payload to the appropriate handler."""
    if event_type == "inflow":
        validated = InflowWebhookPayload(**payload)
        fintech_service.handle_inflow_notification(validated.model_dump())
        return

    if event_type == "upgrade-status":
        validated = UpgradeStatusWebhookPayload(**payload)
        fintech_service.handle_upgrade_status_notification(validated.model_dump())
        return

    _record_webhook(payload, event_type)


@router.post(
    "/notification",
    response_model=ProviderWebhookAckResponse,
    status_code=status.HTTP_200_OK,
    summary="Wallet provider webhook (canonical URL)",
)
async def wallet_notification_webhook(
    request: Request,
    _: str = Depends(verify_webhook_basic_auth),
):
    """
    Canonical webhook endpoint for third-party wallet notifications.

    Requires HTTP Basic Authentication. Returns the provider-required
    acknowledgement format on success.
    """
    try:
        payload = await _extract_payload(request)
        event_type = _classify_event(payload)
        _process_webhook_payload(payload, event_type)
        logger.info("Processed wallet webhook event type=%s", event_type)
        return webhook_ack_response()
    except ValidationError as e:
        first_error = e.errors()[0] if e.errors() else {}
        field = ".".join(str(part) for part in first_error.get("loc", []))
        message = f"Validation failed: {field} - {first_error.get('msg', 'invalid value')}"
        logger.error("Wallet webhook validation failed: %s", message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "status": "error", "code": "01", "message": message},
        )
    except ValueError as e:
        logger.error("Wallet webhook processing failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "status": "error", "code": "01", "message": str(e)},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Wallet webhook error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "status": "error", "code": "99", "message": "Webhook processing failed"},
        )


@router.post(
    "/9psb",
    response_model=ProviderWebhookAckResponse,
    status_code=status.HTTP_200_OK,
    summary="Legacy 9PSB webhook alias",
)
async def nine_psb_webhook(
    request: Request,
    _: str = Depends(verify_webhook_basic_auth),
):
    """
    Legacy alias that stores and processes 9PSB callbacks using the same
    authentication and acknowledgement contract as /notification.
    """
    try:
        payload = await _extract_payload(request)
        event_type = _classify_event(payload)
        _process_webhook_payload(payload, event_type)
        logger.info("Processed 9PSB webhook event type=%s", event_type)
        return webhook_ack_response()
    except ValidationError as e:
        first_error = e.errors()[0] if e.errors() else {}
        field = ".".join(str(part) for part in first_error.get("loc", []))
        message = f"Validation failed: {field} - {first_error.get('msg', 'invalid value')}"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "status": "error", "code": "01", "message": message},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to store 9PSB webhook: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "status": "error", "code": "99", "message": "Failed to store 9PSB webhook"},
        )
