"""
src/agents/hiring_manager.py  (AM-35)
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.db import get_db
from src.shared.models import Company, SpecialistHire
from src.shared.exceptions import CompanyNotFoundError, GovernanceError, AgentNotFoundError
from src.shared.schemas import SpecialistHireSchema
from src.core import audit_log
from src.agents.base_agent import BaseAgent


async def _get_company_id(slug: str, session: AsyncSession) -> uuid.UUID:
    result = await session.execute(select(Company.id).where(Company.slug == slug))
    row = result.scalar_one_or_none()
    if row is None:
        raise CompanyNotFoundError(slug)
    return row


async def _get_hire(hire_id: str, session: AsyncSession) -> SpecialistHire:
    hid = uuid.UUID(hire_id)
    result = await session.execute(select(SpecialistHire).where(SpecialistHire.id == hid))
    hire = result.scalar_one_or_none()
    if hire is None:
        raise GovernanceError(f"Specialist hire '{hire_id}' not found.")
    return hire


async def propose_hire(
    company_slug: str,
    specialist_type: str,
    problem_statement: str,
    budget_usd: float,
    success_criteria: str,
    db: AsyncSession | None = None,
) -> str:
    # Validate specialist_type is known
    from src.agents.registry import _TEMPLATE_REGISTRY
    if specialist_type not in _TEMPLATE_REGISTRY:
        raise AgentNotFoundError(specialist_type, company_slug)

    async def _run(session: AsyncSession) -> str:
        company_id = await _get_company_id(company_slug, session)
        hire = SpecialistHire(
            id=uuid.uuid4(),
            company_id=company_id,
            specialist_type=specialist_type,
            status="proposed",
            problem_statement=problem_statement,
            success_criteria=success_criteria,
            budget_allocated=budget_usd,
            budget_spent=0.0,
        )
        session.add(hire)
        await session.flush()
        hire_id = str(hire.id)
        await audit_log.write_raw(
            company_id=company_slug,
            agent_slug="hiring_manager",
            action="specialist.proposed",
            payload={"hire_id": hire_id, "type": specialist_type, "budget": budget_usd},
        )
        await session.commit()
        return hire_id

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def get_pending_proposals(
    company_slug: str, db: AsyncSession | None = None
) -> list[SpecialistHireSchema]:
    async def _run(session: AsyncSession) -> list[SpecialistHireSchema]:
        company_id = await _get_company_id(company_slug, session)
        result = await session.execute(
            select(SpecialistHire).where(
                SpecialistHire.company_id == company_id,
                SpecialistHire.status == "proposed",
            )
        )
        hires = list(result.scalars().all())
        return [_to_schema(h, company_slug) for h in hires]

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def approve_hire(
    hire_id: str, approved_by: str, db: AsyncSession | None = None
) -> None:
    async def _run(session: AsyncSession) -> None:
        hire = await _get_hire(hire_id, session)
        if hire.status != "proposed":
            raise GovernanceError(
                f"Cannot approve hire in status '{hire.status}'. Must be 'proposed'."
            )
        hire.status = "approved"
        hire.approved_by = approved_by
        hire.updated_at = datetime.now(timezone.utc)
        await audit_log.write_raw(
            company_id=str(hire.company_id),
            agent_slug="hiring_manager",
            action="specialist.approved",
            payload={"hire_id": hire_id, "approved_by": approved_by},
        )
        await session.commit()

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def activate_hire(hire_id: str, db: AsyncSession | None = None) -> BaseAgent:
    async def _run(session: AsyncSession) -> BaseAgent:
        hire = await _get_hire(hire_id, session)
        if hire.status != "approved":
            raise GovernanceError(
                f"Cannot activate hire in status '{hire.status}'. Must be 'approved' first."
            )

        # Get company slug
        company_result = await session.execute(
            select(Company).where(Company.id == hire.company_id)
        )
        company = company_result.scalar_one()
        company_slug = company.slug

        hire.status = "active"
        hire.activated_at = datetime.now(timezone.utc)
        hire.updated_at = datetime.now(timezone.utc)

        await audit_log.write_raw(
            company_id=company_slug,
            agent_slug="hiring_manager",
            action="specialist.activated",
            payload={"hire_id": hire_id, "type": hire.specialist_type},
        )
        await session.commit()

        from src.agents.registry import _TEMPLATE_REGISTRY
        klass = _TEMPLATE_REGISTRY[hire.specialist_type]
        agent_id = f"{company_slug}-{hire.specialist_type}"
        agent = klass(agent_id=agent_id, company_id=company_slug)
        return agent

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def wind_down(
    hire_id: str, outcome_summary: str, db: AsyncSession | None = None
) -> None:
    async def _run(session: AsyncSession) -> None:
        hire = await _get_hire(hire_id, session)
        if hire.status != "active":
            raise GovernanceError(
                f"Cannot wind down hire in status '{hire.status}'. Must be 'active'."
            )
        hire.status = "wound_down"
        hire.wound_down_at = datetime.now(timezone.utc)
        hire.updated_at = datetime.now(timezone.utc)
        hire.proposal_json = {**(hire.proposal_json or {}), "outcome_summary": outcome_summary}

        company_result = await session.execute(
            select(Company.slug).where(Company.id == hire.company_id)
        )
        company_slug = company_result.scalar_one()

        await audit_log.write_raw(
            company_id=company_slug,
            agent_slug="hiring_manager",
            action="specialist.wound_down",
            payload={"hire_id": hire_id, "outcome": outcome_summary},
        )
        await session.commit()

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


def _to_schema(hire: SpecialistHire, company_slug: str) -> SpecialistHireSchema:
    return SpecialistHireSchema(
        id=str(hire.id),
        company_slug=company_slug,
        specialist_type=hire.specialist_type,
        status=hire.status,
        problem_statement=hire.problem_statement,
        success_criteria=hire.success_criteria,
        budget_allocated=float(hire.budget_allocated),
        budget_spent=float(hire.budget_spent),
        approved_by=hire.approved_by,
        activated_at=hire.activated_at.isoformat() if hire.activated_at else None,
        wound_down_at=hire.wound_down_at.isoformat() if hire.wound_down_at else None,
    )
