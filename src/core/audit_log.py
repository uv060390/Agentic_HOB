"""
src/core/audit_log.py  (AM-20)

Append-only audit log writer.
IMPORTANT: This module only ever INSERTs. No UPDATE, no DELETE — ever.
All agent actions that change state must call write() before returning.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select

from src.shared.db import get_db
from src.shared.models import AuditEntry, Company
from src.shared.schemas import AuditEntryCreate

logger = logging.getLogger(__name__)


async def _resolve_company_uuid(company_slug: str) -> uuid.UUID:
    """Look up the Company UUID from its slug."""
    async with get_db() as session:
        result = await session.execute(
            select(Company.id).where(Company.slug == company_slug)
        )
        company_uuid = result.scalar_one_or_none()
        if company_uuid is None:
            raise ValueError(f"Company slug not found: '{company_slug}'")
        return company_uuid  # type: ignore[return-value]


async def write(entry: AuditEntryCreate) -> str:
    """
    Append an audit entry to the database.

    Args:
        entry: Validated AuditEntryCreate schema.

    Returns:
        The UUID of the created audit_entry row (as string).
    """
    company_uuid = await _resolve_company_uuid(entry.company_id)
    ticket_uuid: uuid.UUID | None = (
        uuid.UUID(entry.ticket_id) if entry.ticket_id else None
    )

    async with get_db() as session:
        row = AuditEntry(
            company_id=company_uuid,
            agent_slug=entry.agent_slug,
            action=entry.action,
            payload=entry.payload,
            ticket_id=ticket_uuid,
            goal_ref=entry.goal_ref,
        )
        session.add(row)
        await session.flush()
        entry_id = str(row.id)

    logger.info(
        "audit | company=%s agent=%s action=%s id=%s",
        entry.company_id,
        entry.agent_slug,
        entry.action,
        entry_id,
    )
    return entry_id


async def write_raw(
    company_id: str,
    agent_slug: str,
    action: str,
    payload: dict[str, Any] | None = None,
    ticket_id: str | None = None,
    goal_ref: str | None = None,
) -> str:
    """Convenience wrapper — build AuditEntryCreate inline and write."""
    return await write(
        AuditEntryCreate(
            company_id=company_id,
            agent_slug=agent_slug,
            action=action,
            payload=payload,
            ticket_id=ticket_id,
            goal_ref=goal_ref,
        )
    )
