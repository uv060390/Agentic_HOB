"""
src/tools/tool_registry.py  (AM-57)

Database-driven tool activation per brand with budget-aware gating.
A tool module existing in code does NOT make it available — it must have
an active entry in the tool_registry table.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.db import get_db
from src.shared.exceptions import ToolNotRegisteredError
from src.shared.models import Company, ToolRegistry

logger = logging.getLogger(__name__)


async def _get_company_id(slug: str, session: AsyncSession) -> Any:
    result = await session.execute(select(Company.id).where(Company.slug == slug))
    row = result.scalar_one_or_none()
    if row is None:
        from src.shared.exceptions import CompanyNotFoundError
        raise CompanyNotFoundError(slug)
    return row


async def is_tool_active(
    company_slug: str,
    tool_slug: str,
    db: AsyncSession | None = None,
) -> bool:
    """Check if a tool is active for a brand."""
    async def _run(session: AsyncSession) -> bool:
        company_id = await _get_company_id(company_slug, session)
        result = await session.execute(
            select(ToolRegistry).where(
                ToolRegistry.company_id == company_id,
                ToolRegistry.tool_slug == tool_slug,
                ToolRegistry.is_active == True,
            )
        )
        return result.scalar_one_or_none() is not None

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def get_active_tools(
    company_slug: str,
    db: AsyncSession | None = None,
) -> list[str]:
    """Return list of active tool slugs for a brand."""
    async def _run(session: AsyncSession) -> list[str]:
        company_id = await _get_company_id(company_slug, session)
        result = await session.execute(
            select(ToolRegistry.tool_slug).where(
                ToolRegistry.company_id == company_id,
                ToolRegistry.is_active == True,
            )
        )
        return [row for row in result.scalars().all()]

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def assert_tool_active(company_slug: str, tool_slug: str) -> None:
    """Raise ToolNotRegisteredError if the tool is not active for the brand."""
    if not await is_tool_active(company_slug, tool_slug):
        raise ToolNotRegisteredError(tool_slug, company_slug)


async def register_tool(
    company_slug: str,
    tool_slug: str,
    monthly_budget_cap_usd: float = 0.0,
    db: AsyncSession | None = None,
) -> str:
    """Register and activate a tool for a brand. Returns the registry entry ID."""
    async def _run(session: AsyncSession) -> str:
        company_id = await _get_company_id(company_slug, session)
        # Upsert: check if entry already exists
        result = await session.execute(
            select(ToolRegistry).where(
                ToolRegistry.company_id == company_id,
                ToolRegistry.tool_slug == tool_slug,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.is_active = True
            existing.monthly_budget_cap_usd = monthly_budget_cap_usd
            await session.flush()
            return str(existing.id)

        entry = ToolRegistry(
            company_id=company_id,
            tool_slug=tool_slug,
            is_active=True,
            monthly_budget_cap_usd=monthly_budget_cap_usd,
        )
        session.add(entry)
        await session.flush()
        return str(entry.id)

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def deactivate_tool(
    company_slug: str,
    tool_slug: str,
    db: AsyncSession | None = None,
) -> None:
    """Deactivate a tool for a brand."""
    async def _run(session: AsyncSession) -> None:
        company_id = await _get_company_id(company_slug, session)
        result = await session.execute(
            select(ToolRegistry).where(
                ToolRegistry.company_id == company_id,
                ToolRegistry.tool_slug == tool_slug,
            )
        )
        entry = result.scalar_one_or_none()
        if entry is not None:
            entry.is_active = False
            await session.flush()

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)
