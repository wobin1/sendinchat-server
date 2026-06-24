from datetime import datetime
import json
from typing import Any, Dict, Optional

import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.packages.fintech.service import JsonDatabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fintech/webhooks", tags=["fintech-webhooks"])


def _classify_event(payload: Dict[str, Any]) -> str:
    """Best-effort classification for a 9PSB callback payload."""
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
        or f"9psb-webhook-{datetime.utcnow().timestamp()}",
        "source": "9PSB",
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
                detail={"status": "error", "message": "Webhook body must be valid JSON", "data": None},
            )
        if not isinstance(parsed, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Webhook payload must be a JSON object", "data": None},
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
            detail={"status": "error", "message": "Webhook body must be valid JSON", "data": None},
        )
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": "Webhook payload must be a JSON object", "data": None},
        )
    return parsed


@router.post("/9psb")
async def nine_psb_webhook(request: Request):
    """
    Store an incoming 9PSB webhook payload without changing any existing webhook behavior.

    This endpoint saves the raw JSON body to the local JSON database and tags it as
    `inflow`, `upgrade-status`, or `raw` when it can infer the event type.
    """
    try:
        payload = await _extract_payload(request)

        event_type = _classify_event(payload)
        record = _record_webhook(payload, event_type)
        logger.info("Stored 9PSB webhook event type=%s id=%s", event_type, record["id"])

        return {
            "status": "received",
            "message": "9PSB webhook stored successfully",
            "data": {
                "id": record["id"],
                "source": "9PSB",
                "eventType": event_type,
                "payload": payload,
                "receivedAt": record["receivedAt"],
                "transactionReference": payload.get("transactionReference"),
                "accountNumber": payload.get("accountNumber"),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to store 9PSB webhook: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to store 9PSB webhook", "data": None},
        )
