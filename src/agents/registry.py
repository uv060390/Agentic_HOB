"""
src/agents/registry.py  (AM-34)
"""
from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.db import get_db
from src.shared.models import AgentConfig, Company, SpecialistHire
from src.shared.exceptions import AgentNotFoundError, CompanyNotFoundError
from src.agents.base_agent import BaseAgent
from src.agents.templates.ceo import CEOAgent
from src.agents.templates.finance import FinanceAgent
from src.agents.templates.scout import ScoutAgent
from src.agents.templates.cmo import CMOAgent
from src.agents.templates.creative import CreativeAgent
from src.agents.templates.performance import PerformanceAgent
from src.agents.templates.ops import OpsAgent
from src.agents.holdco.portfolio_cfo import PortfolioCFOAgent
from src.agents.holdco.bd_agent import BDAgent
from src.agents.specialists.data_scientist import DataScientistAgent
from src.agents.specialists.engineer import EngineerAgent
from src.agents.specialists.data_analyst import DataAnalystAgent
from src.agents.specialists.optimizer import OptimizerAgent
from src.agents.specialists.seo_aeo import SEOAEOAgent
from src.agents.specialists.growth_hacker import GrowthHackerAgent

_TEMPLATE_REGISTRY: dict[str, type[BaseAgent]] = {
    "ceo": CEOAgent,
    "finance": FinanceAgent,
    "scout": ScoutAgent,
    "cmo": CMOAgent,
    "creative": CreativeAgent,
    "performance": PerformanceAgent,
    "ops": OpsAgent,
    "portfolio_cfo": PortfolioCFOAgent,
    "bd": BDAgent,
    "data_scientist": DataScientistAgent,
    "engineer": EngineerAgent,
    "data_analyst": DataAnalystAgent,
    "optimizer": OptimizerAgent,
    "seo_aeo": SEOAEOAgent,
    "growth_hacker": GrowthHackerAgent,
}


def _instantiate(cfg: AgentConfig, company_slug: str) -> BaseAgent:
    template = cfg.agent_template or cfg.agent_slug.split("-")[-1]
    klass = _TEMPLATE_REGISTRY.get(template)
    if klass is None:
        raise AgentNotFoundError(cfg.agent_slug, company_slug)
    # Standing agents use simple constructor; specialists need agent_id + company_id
    try:
        return klass(agent_id=cfg.agent_slug, company_id=company_slug)
    except TypeError:
        return klass(cfg.agent_slug, company_slug)


async def _get_company_id(slug: str, session: AsyncSession):
    result = await session.execute(select(Company.id).where(Company.slug == slug))
    row = result.scalar_one_or_none()
    if row is None:
        raise CompanyNotFoundError(slug)
    return row


async def get_agent_instance(
    agent_slug: str, company_slug: str, db: AsyncSession | None = None
) -> BaseAgent:
    async def _run(session: AsyncSession) -> BaseAgent:
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
        return _instantiate(cfg, company_slug)

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def get_standing_team(
    company_slug: str, db: AsyncSession | None = None
) -> list[BaseAgent]:
    async def _run(session: AsyncSession) -> list[BaseAgent]:
        company_id = await _get_company_id(company_slug, session)
        result = await session.execute(
            select(AgentConfig).where(
                AgentConfig.company_id == company_id,
                AgentConfig.is_specialist == False,
                AgentConfig.is_active == True,
            )
        )
        configs = list(result.scalars().all())
        return [_instantiate(cfg, company_slug) for cfg in configs]

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def get_active_specialists(
    company_slug: str, db: AsyncSession | None = None
) -> list[BaseAgent]:
    async def _run(session: AsyncSession) -> list[BaseAgent]:
        company_id = await _get_company_id(company_slug, session)
        result = await session.execute(
            select(SpecialistHire).where(
                SpecialistHire.company_id == company_id,
                SpecialistHire.status == "active",
            )
        )
        hires = list(result.scalars().all())
        agents: list[BaseAgent] = []
        for hire in hires:
            cfg_result = await session.execute(
                select(AgentConfig).where(
                    AgentConfig.company_id == company_id,
                    AgentConfig.agent_slug == hire.specialist_type,
                )
            )
            cfg = cfg_result.scalar_one_or_none()
            if cfg:
                agent = _instantiate(cfg, company_slug)
            else:
                klass = _TEMPLATE_REGISTRY.get(hire.specialist_type)
                if klass is None:
                    continue
                agent = klass(agent_id=f"{company_slug}-{hire.specialist_type}", company_id=company_slug)
                if hire.wound_down_at:
                    agent.wound_down_at = hire.wound_down_at
            agents.append(agent)
        return agents

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)
