"""
src/core/org_chart.py  (AM-29)
"""
from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.db import get_db
from src.shared.models import AgentConfig, Company, SpecialistHire
from src.shared.exceptions import AgentNotFoundError, CompanyNotFoundError
from src.shared.schemas import OrgChartSchema


async def _get_company_id(slug: str, session: AsyncSession):
    result = await session.execute(select(Company.id).where(Company.slug == slug))
    row = result.scalar_one_or_none()
    if row is None:
        raise CompanyNotFoundError(slug)
    return row


async def get_org_chart(company_slug: str, db: AsyncSession | None = None) -> OrgChartSchema:
    async def _run(session: AsyncSession) -> OrgChartSchema:
        company_id = await _get_company_id(company_slug, session)
        result = await session.execute(
            select(AgentConfig).where(AgentConfig.company_id == company_id)
        )
        all_agents = list(result.scalars().all())

        standing = [a for a in all_agents if not a.is_specialist]
        # active specialists via specialist_hire table
        sh_result = await session.execute(
            select(SpecialistHire).where(
                SpecialistHire.company_id == company_id,
                SpecialistHire.status == "active",
            )
        )
        active_hires = list(sh_result.scalars().all())
        active_slugs = {h.specialist_type for h in active_hires}
        specialists = [a for a in all_agents if a.is_specialist and a.agent_slug in active_slugs]

        reporting_lines: dict[str, list[str]] = {}
        for agent in all_agents:
            if agent.reports_to_slug:
                reporting_lines.setdefault(agent.reports_to_slug, []).append(agent.agent_slug)

        return OrgChartSchema(
            company_slug=company_slug,
            standing_agents=[
                {"slug": a.agent_slug, "template": a.agent_template, "model_tier": a.model_tier}
                for a in standing
            ],
            active_specialists=[
                {"slug": a.agent_slug, "template": a.agent_template}
                for a in specialists
            ],
            reporting_lines=reporting_lines,
        )

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def get_agent_config(
    agent_slug: str, company_slug: str, db: AsyncSession | None = None
) -> AgentConfig:
    async def _run(session: AsyncSession) -> AgentConfig:
        company_id = await _get_company_id(company_slug, session)
        result = await session.execute(
            select(AgentConfig).where(
                AgentConfig.agent_slug == agent_slug,
                AgentConfig.company_id == company_id,
            )
        )
        cfg = result.scalar_one_or_none()
        if cfg is None:
            raise AgentNotFoundError(agent_slug, company_slug)
        return cfg

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def get_standing_agents(
    company_slug: str, db: AsyncSession | None = None
) -> list[AgentConfig]:
    async def _run(session: AsyncSession) -> list[AgentConfig]:
        company_id = await _get_company_id(company_slug, session)
        result = await session.execute(
            select(AgentConfig).where(
                AgentConfig.company_id == company_id,
                AgentConfig.is_specialist == False,
            )
        )
        return list(result.scalars().all())

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def get_specialists(
    company_slug: str, db: AsyncSession | None = None
) -> list[AgentConfig]:
    async def _run(session: AsyncSession) -> list[AgentConfig]:
        company_id = await _get_company_id(company_slug, session)
        result = await session.execute(
            select(AgentConfig).where(
                AgentConfig.company_id == company_id,
                AgentConfig.is_specialist == True,
            )
        )
        return list(result.scalars().all())

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def get_reports_to(
    agent_slug: str, company_slug: str, db: AsyncSession | None = None
) -> list[AgentConfig]:
    async def _run(session: AsyncSession) -> list[AgentConfig]:
        company_id = await _get_company_id(company_slug, session)
        result = await session.execute(
            select(AgentConfig).where(
                AgentConfig.company_id == company_id,
                AgentConfig.reports_to_slug == agent_slug,
            )
        )
        return list(result.scalars().all())

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)
