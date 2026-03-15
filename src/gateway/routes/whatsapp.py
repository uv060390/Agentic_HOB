"""
src/gateway/routes/whatsapp.py  (AM-80)

WhatsApp Business API webhook handler.
Handles verification (GET) and incoming messages (POST).
All incoming message content passes through the sanitizer.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse

from src.gateway.auth import require_api_key
from src.gateway.sanitizer import sanitize
from src.shared.config import get_settings
from src.shared.schemas import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/whatsapp", tags=["whatsapp"])


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
) -> PlainTextResponse:
    """WhatsApp webhook verification (GET)."""
    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        logger.info("WhatsApp webhook verified")
        return PlainTextResponse(content=hub_challenge or "")
    logger.warning("WhatsApp webhook verification failed")
    return PlainTextResponse(content="Verification failed", status_code=403)


@router.post("/webhook")
async def receive_message(request: Request) -> ApiResponse[dict[str, Any]]:
    """Handle incoming WhatsApp messages."""
    body = await request.json()

    # Extract message from WhatsApp webhook payload
    message_text = ""
    sender = ""
    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        if messages:
            msg = messages[0]
            message_text = msg.get("text", {}).get("body", "")
            sender = msg.get("from", "")
    except (IndexError, KeyError):
        logger.warning("Could not parse WhatsApp webhook payload")
        return ApiResponse.success({"status": "no_message"})

    if not message_text:
        return ApiResponse.success({"status": "no_text"})

    # Sanitize incoming message
    sanitized = sanitize(message_text, source="whatsapp")

    logger.info("WhatsApp message received | from=%s len=%d", sender, len(sanitized))

    # Dispatch through intent router
    from src.gateway.intent_router import dispatch
    result = await dispatch(message=sanitized, founder_id=sender, channel="whatsapp")

    return ApiResponse.success({
        "status": "processed",
        "response": result.output[:1000],
        "ticket_id": result.ticket_id,
    })
