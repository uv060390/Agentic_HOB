"""
src/core/ticket_system.py  (AM-31)
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.db import get_db
from src.shared.models import Ticket, Company
from src.shared.exceptions import TicketNotFoundError, CompanyNotFoundError
from src.core import audit_log
from src.shared.schemas import AuditEntryCreate


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


async def _get_company_id(slug: str, session: AsyncSession) -> uuid.UUID:
    result = await session.execute(select(Company.id).where(Company.slug == slug))
    row = result.scalar_one_or_none()
    if row is None:
        raise CompanyNotFoundError(slug)
    return row


async def create_ticket(
    company_slug: str,
    agent_slug: str,
    summary: str,
    description: str = "",
    task_type: str | None = None,
    db: AsyncSession | None = None,
) -> str:
    async def _run(session: AsyncSession) -> str:
        company_id = await _get_company_id(company_slug, session)
        ticket = Ticket(
            id=uuid.uuid4(),
            company_id=company_id,
            title=summary,
            status=TicketStatus.OPEN.value,
            owner_agent_slug=agent_slug,
            thread=[],
            result=None,
        )
        if hasattr(ticket, "description"):
            ticket.description = description  # type: ignore[assignment]
        if hasattr(ticket, "task_type"):
            ticket.task_type = task_type  # type: ignore[assignment]
        session.add(ticket)
        await session.flush()
        ticket_id = str(ticket.id)
        await audit_log.write(AuditEntryCreate(
            company_id=company_slug,
            agent_slug=agent_slug,
            action="ticket.created",
            payload={"ticket_id": ticket_id, "summary": summary},
            ticket_id=ticket_id,
        ))
        await session.commit()
        return ticket_id

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def update_ticket(
    ticket_id: str,
    status: str | None = None,
    description: str | None = None,
    db: AsyncSession | None = None,
) -> None:
    async def _run(session: AsyncSession) -> None:
        tid = uuid.UUID(ticket_id)
        result = await session.execute(select(Ticket).where(Ticket.id == tid))
        ticket = result.scalar_one_or_none()
        if ticket is None:
            raise TicketNotFoundError(ticket_id)
        if status is not None:
            ticket.status = status
        if description is not None and hasattr(ticket, "description"):
            ticket.description = description  # type: ignore[assignment]
        ticket.updated_at = datetime.now(timezone.utc)
        await session.commit()

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def add_thread_message(
    ticket_id: str,
    message: str,
    author_agent_slug: str,
    db: AsyncSession | None = None,
) -> None:
    async def _run(session: AsyncSession) -> None:
        tid = uuid.UUID(ticket_id)
        result = await session.execute(select(Ticket).where(Ticket.id == tid))
        ticket = result.scalar_one_or_none()
        if ticket is None:
            raise TicketNotFoundError(ticket_id)
        thread = list(ticket.thread or [])
        thread.append({
            "author": author_agent_slug,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        ticket.thread = thread
        ticket.updated_at = datetime.now(timezone.utc)
        await session.commit()

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def close_ticket(
    ticket_id: str,
    resolution: str,
    db: AsyncSession | None = None,
) -> None:
    async def _run(session: AsyncSession) -> None:
        tid = uuid.UUID(ticket_id)
        result = await session.execute(select(Ticket).where(Ticket.id == tid))
        ticket = result.scalar_one_or_none()
        if ticket is None:
            raise TicketNotFoundError(ticket_id)
        ticket.status = TicketStatus.RESOLVED.value
        if hasattr(ticket, "resolution"):
            ticket.resolution = resolution  # type: ignore[assignment]
        else:
            ticket.result = {"resolution": resolution}
        ticket.updated_at = datetime.now(timezone.utc)
        await session.commit()

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def get_ticket(ticket_id: str, db: AsyncSession | None = None) -> Ticket:
    async def _run(session: AsyncSession) -> Ticket:
        tid = uuid.UUID(ticket_id)
        result = await session.execute(select(Ticket).where(Ticket.id == tid))
        ticket = result.scalar_one_or_none()
        if ticket is None:
            raise TicketNotFoundError(ticket_id)
        return ticket

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def list_open_tickets(company_slug: str, db: AsyncSession | None = None) -> list[Ticket]:
    async def _run(session: AsyncSession) -> list[Ticket]:
        company_id = await _get_company_id(company_slug, session)
        result = await session.execute(
            select(Ticket).where(
                Ticket.company_id == company_id,
                Ticket.status != TicketStatus.RESOLVED.value,
            )
        )
        return list(result.scalars().all())

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)
