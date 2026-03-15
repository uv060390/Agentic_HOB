"""
src/gateway/routes/telegram.py  (AM-81)

Telegram Bot API webhook handler.
Handles incoming messages via webhook POST.
All incoming message content passes through the sanitizer.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

from src.gateway.sanitizer import sanitize
from src.shared.schemas import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/telegram", tags=["telegram"])


@router.post("/webhook")
async def receive_update(request: Request) -> ApiResponse[dict[str, Any]]:
    """Handle incoming Telegram updates (messages)."""
    body = await request.json()

    # Extract message from Telegram webhook payload
    message = body.get("message", {})
    text = message.get("text", "")
    chat = message.get("chat", {})
    sender_id = str(chat.get("id", ""))
    username = message.get("from", {}).get("username", "")

    if not text:
        return ApiResponse.success({"status": "no_text"})

    # Sanitize incoming message
    sanitized = sanitize(text, source="telegram")

    logger.info(
        "Telegram message received | from=%s user=%s len=%d",
        sender_id, username, len(sanitized),
    )

    # Dispatch through intent router
    from src.gateway.intent_router import dispatch
    result = await dispatch(message=sanitized, founder_id=sender_id, channel="telegram")

    return ApiResponse.success({
        "status": "processed",
        "response": result.output[:1000],
        "ticket_id": result.ticket_id,
    })
