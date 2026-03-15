"""
src/gateway/routes/onboarding.py  (AM-108)

FastAPI route handler for the BrandOS onboarding wizard.

Called by WhatsApp / Telegram webhook handlers when the intent router detects
that the incoming founder has no company configured yet.

Endpoints:
  POST /api/v1/onboarding/message           — process a founder message
  GET  /api/v1/onboarding/status/{founder_id} — admin: inspect session state
  POST /api/v1/onboarding/reset/{founder_id}  — admin: restart session

DB access uses raw SQL against the `onboarding_session` table (migration 0004).
No ORM model — keeps this layer thin and avoids circular imports from the
model layer touching onboarding at import time.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from src.core.onboarding import process_input, total_step_count
from src.gateway.auth import require_api_key
from src.shared.db import get_db
from src.shared.schemas import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


# ── Request / Response models ─────────────────────────────────────────────────


class OnboardingMessageRequest(BaseModel):
    founder_id: str          # Telegram chat_id (str) or WhatsApp phone number
    channel: str             # "telegram" | "whatsapp"
    message: str             # Raw message text from the founder


class OnboardingMessageResponse(BaseModel):
    reply: str
    step_advanced: bool
    current_step_id: str
    is_complete: bool
    progress: str            # e.g. "Step 4 of 18"


class OnboardingStatusResponse(BaseModel):
    session_id: str
    founder_id: str
    channel: str
    status: str
    current_step_id: str
    completed_steps: list[str]
    collected_config: dict[str, Any]   # non-sensitive only
    pending_tool_steps: list[str]
    error_message: str | None
    last_message_at: str
    created_at: str


# ── DB helpers ────────────────────────────────────────────────────────────────

_SELECT_SESSION = text("""
    SELECT id, founder_id, channel, status, current_step_id,
           completed_steps, collected_config, pending_tool_steps,
           company_id, error_message, last_message_at, created_at, updated_at
    FROM onboarding_session
    WHERE founder_id = :founder_id
    ORDER BY created_at DESC
    LIMIT 1
""")

_INSERT_SESSION = text("""
    INSERT INTO onboarding_session
        (id, founder_id, channel, status, current_step_id,
         completed_steps, collected_config, pending_tool_steps,
         last_message_at)
    VALUES
        (:id, :founder_id, :channel, 'in_progress', 'welcome',
         '[]', '{}', '[]',
         now())
    RETURNING id, founder_id, channel, status, current_step_id,
              completed_steps, collected_config, pending_tool_steps,
              company_id, error_message, last_message_at, created_at, updated_at
""")

_UPDATE_SESSION_FIELDS = text("""
    UPDATE onboarding_session
    SET
        status            = COALESCE(:status, status),
        current_step_id   = COALESCE(:current_step_id, current_step_id),
        completed_steps   = COALESCE(:completed_steps, completed_steps),
        collected_config  = COALESCE(:collected_config, collected_config),
        pending_tool_steps = COALESCE(:pending_tool_steps, pending_tool_steps),
        error_message     = :error_message,
        last_message_at   = now(),
        completed_at      = CASE WHEN :status = 'complete' THEN now() ELSE completed_at END,
        updated_at        = now()
    WHERE id = :session_id
""")


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Map a SQLAlchemy Row to a plain dict with JSON columns decoded."""
    d = dict(row._mapping)  # noqa: SLF001
    for key in ("completed_steps", "collected_config", "pending_tool_steps"):
        if isinstance(d.get(key), str):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                d[key] = [] if key != "collected_config" else {}
    # Normalise UUIDs to str
    if d.get("id") is not None:
        d["id"] = str(d["id"])
    if d.get("company_id") is not None:
        d["company_id"] = str(d["company_id"])
    # Normalise timestamps to ISO strings
    for ts_key in ("last_message_at", "created_at", "updated_at", "completed_at"):
        val = d.get(ts_key)
        if val is not None and hasattr(val, "isoformat"):
            d[ts_key] = val.isoformat()
    return d


async def _get_or_create_session(
    db: Any,
    founder_id: str,
    channel: str,
) -> dict[str, Any]:
    """
    Return the most recent active onboarding session for this founder,
    or create a new one if none exists (or the last was completed/abandoned).
    """
    result = await db.execute(_SELECT_SESSION, {"founder_id": founder_id})
    row = result.fetchone()
    if row:
        session = _row_to_dict(row)
        # If the previous session completed or was abandoned, start fresh
        if session["status"] in ("complete", "abandoned"):
            new_id = str(uuid.uuid4())
            result = await db.execute(
                _INSERT_SESSION,
                {"id": new_id, "founder_id": founder_id, "channel": channel},
            )
            session = _row_to_dict(result.fetchone())
        return session

    # First-time founder
    new_id = str(uuid.uuid4())
    result = await db.execute(
        _INSERT_SESSION,
        {"id": new_id, "founder_id": founder_id, "channel": channel},
    )
    return _row_to_dict(result.fetchone())


async def _persist_updates(
    db: Any,
    session_id: str,
    updates: dict[str, Any],
) -> None:
    """Write updated session fields back to the DB."""
    if not updates:
        return
    await db.execute(
        _UPDATE_SESSION_FIELDS,
        {
            "session_id": session_id,
            "status": updates.get("status"),
            "current_step_id": updates.get("current_step_id"),
            "completed_steps": (
                json.dumps(updates["completed_steps"])
                if "completed_steps" in updates
                else None
            ),
            "collected_config": (
                json.dumps(updates["collected_config"])
                if "collected_config" in updates
                else None
            ),
            "pending_tool_steps": (
                json.dumps(updates["pending_tool_steps"])
                if "pending_tool_steps" in updates
                else None
            ),
            "error_message": updates.get("error_message"),
        },
    )


# ── Message formatting ────────────────────────────────────────────────────────

_MARKDOWN_LINK_RE = re.compile(r"\[(.+?)\]\(.+?\)")


def format_for_channel(text: str, channel: str) -> str:
    """
    WhatsApp uses its own limited markdown (bold = *text*) which differs from
    Telegram's MarkdownV2. For WhatsApp we strip unsupported formatting;
    for Telegram we pass the text through unchanged (bot uses parse_mode=Markdown).
    """
    if channel == "whatsapp":
        # WhatsApp supports *bold* natively — keep it.
        # Strip markdown links → show plain URL or link text.
        text = _MARKDOWN_LINK_RE.sub(r"\1", text)
    return text


def _progress_line(session: dict[str, Any]) -> str:
    """Return a progress footer like '[Step 4 of 18]'."""
    completed = session.get("completed_steps") or []
    current = session.get("current_step_id", "welcome")
    if current in ("complete",):
        return ""
    step_num = len(completed) + 1
    total = total_step_count(session.get("collected_config") or {})
    return f"\n\n[Step {step_num} of {total}]"


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post(
    "/message",
    response_model=ApiResponse[OnboardingMessageResponse],
    summary="Process a founder message during onboarding",
)
async def handle_onboarding_message(
    body: OnboardingMessageRequest,
    _key: str = Depends(require_api_key),
) -> ApiResponse[OnboardingMessageResponse]:
    """
    Core onboarding message handler.

    1. Load or create an onboarding session for this founder.
    2. Pass the raw message to process_input() (sanitizes + advances step machine).
    3. Persist the updated session fields.
    4. Return the formatted reply for the calling webhook handler to send.
    """
    async with get_db() as db:
        session = await _get_or_create_session(db, body.founder_id, body.channel)
        session_id: str = session["id"]

        # If already complete, short-circuit
        if session["status"] == "complete":
            return ApiResponse.success(
                OnboardingMessageResponse(
                    reply=format_for_channel(
                        "Your BrandOS setup is already complete. "
                        "Your agent team is live and running.",
                        body.channel,
                    ),
                    step_advanced=False,
                    current_step_id="complete",
                    is_complete=True,
                    progress="",
                )
            )

        try:
            reply_text, advanced, updates = await process_input(session, body.message)
        except Exception as exc:
            logger.exception("process_input error for founder %s: %s", body.founder_id, exc)
            return ApiResponse.failure(f"Onboarding error: {exc}")

        # Merge updates back into session dict for accurate progress display
        merged = {**session, **updates}

        await _persist_updates(db, session_id, updates)

    current_step_id: str = merged.get("current_step_id", "welcome")
    is_complete = current_step_id == "complete" or merged.get("status") == "complete"

    progress = "" if is_complete else _progress_line(merged)
    formatted_reply = format_for_channel(reply_text + progress, body.channel)

    return ApiResponse.success(
        OnboardingMessageResponse(
            reply=formatted_reply,
            step_advanced=advanced,
            current_step_id=current_step_id,
            is_complete=is_complete,
            progress=progress.strip(),
        )
    )


@router.get(
    "/status/{founder_id}",
    response_model=ApiResponse[OnboardingStatusResponse],
    summary="Get onboarding session state (admin)",
)
async def get_onboarding_status(
    founder_id: str,
    _key: str = Depends(require_api_key),
) -> ApiResponse[OnboardingStatusResponse]:
    """Return the current onboarding session for a founder (admin/debug use)."""
    async with get_db() as db:
        result = await db.execute(_SELECT_SESSION, {"founder_id": founder_id})
        row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No onboarding session found for founder '{founder_id}'.",
        )

    session = _row_to_dict(row)
    return ApiResponse.success(
        OnboardingStatusResponse(
            session_id=session["id"],
            founder_id=session["founder_id"],
            channel=session["channel"],
            status=session["status"],
            current_step_id=session["current_step_id"],
            completed_steps=session.get("completed_steps") or [],
            collected_config=session.get("collected_config") or {},
            pending_tool_steps=session.get("pending_tool_steps") or [],
            error_message=session.get("error_message"),
            last_message_at=session.get("last_message_at", ""),
            created_at=session.get("created_at", ""),
        )
    )


@router.post(
    "/reset/{founder_id}",
    response_model=ApiResponse[dict],
    summary="Reset onboarding session (admin)",
)
async def reset_onboarding_session(
    founder_id: str,
    _key: str = Depends(require_api_key),
) -> ApiResponse[dict]:
    """
    Mark the current session as abandoned and create a fresh one.
    The old session data is preserved in the DB for audit purposes.
    """
    async with get_db() as db:
        result = await db.execute(_SELECT_SESSION, {"founder_id": founder_id})
        row = result.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No onboarding session found for founder '{founder_id}'.",
            )

        session = _row_to_dict(row)
        if session["status"] == "in_progress":
            # Mark old session abandoned
            await db.execute(
                text(
                    "UPDATE onboarding_session SET status = 'abandoned', updated_at = now() "
                    "WHERE id = :session_id"
                ),
                {"session_id": session["id"]},
            )

    return ApiResponse.success({"reset": True, "founder_id": founder_id})


# ── Public helper used by intent_router ───────────────────────────────────────


async def is_onboarding_complete(founder_id: str) -> bool:
    """
    Returns True if this founder has a completed onboarding session in the DB.
    Called by intent_router before dispatching to agent layer.
    """
    async with get_db() as db:
        result = await db.execute(_SELECT_SESSION, {"founder_id": founder_id})
        row = result.fetchone()
    if not row:
        return False
    session = _row_to_dict(row)
    return session["status"] == "complete"


async def needs_onboarding(founder_id: str) -> bool:
    """
    Returns True if this founder has no complete onboarding session.
    Used by the intent router to decide whether to route to onboarding.
    """
    return not await is_onboarding_complete(founder_id)
