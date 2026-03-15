"""
src/core/goal_ancestry.py  (AM-30)
"""
from __future__ import annotations
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.db import get_db
from src.shared.models import Ticket, Company
from src.shared.exceptions import TicketNotFoundError, CompanyNotFoundError
from src.shared.schemas import GoalAncestry


async def trace_goal(ticket_id: str, db: AsyncSession | None = None) -> GoalAncestry:
    async def _run(session: AsyncSession) -> GoalAncestry:
        try:
            tid = uuid.UUID(ticket_id)
        except ValueError:
            raise TicketNotFoundError(ticket_id)

        result = await session.execute(select(Ticket).where(Ticket.id == tid))
        ticket = result.scalar_one_or_none()
        if ticket is None:
            raise TicketNotFoundError(ticket_id)

        company_result = await session.execute(
            select(Company).where(Company.id == ticket.company_id)
        )
        company = company_result.scalar_one_or_none()
        if company is None:
            raise CompanyNotFoundError(str(ticket.company_id))

        return GoalAncestry(
            ticket_id=str(ticket.id),
            ticket_summary=ticket.title,
            project_name=getattr(ticket, "project_name", None),
            company_slug=company.slug,
            company_name=company.name,
            mission=company.mission,
        )

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def get_company_mission(company_slug: str, db: AsyncSession | None = None) -> str | None:
    async def _run(session: AsyncSession) -> str | None:
        result = await session.execute(
            select(Company.mission).where(Company.slug == company_slug)
        )
        row = result.scalar_one_or_none()
        return row

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)
