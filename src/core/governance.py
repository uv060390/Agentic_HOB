"""
src/core/governance.py  (AM-39)
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.db import get_db
from src.shared.models import AgentConfig, AuditEntry, Company
from src.shared.exceptions import (
    GovernanceError,
    ImmutableAuditError,
    CompanyNotFoundError,
    AgentNotFoundError,
)
from src.core import audit_log


async def _get_company_id(slug: str, session: AsyncSession) -> uuid.UUID:
    result = await session.execute(select(Company.id).where(Company.slug == slug))
    row = result.scalar_one_or_none()
    if row is None:
        raise CompanyNotFoundError(slug)
    return row


async def _get_agent_config(
    agent_slug: str, company_id: uuid.UUID, session: AsyncSession
) -> AgentConfig:
    result = await session.execute(
        select(AgentConfig).where(
            AgentConfig.agent_slug == agent_slug,
            AgentConfig.company_id == company_id,
        )
    )
    cfg = result.scalar_one_or_none()
    if cfg is None:
        raise AgentNotFoundError(agent_slug, str(company_id))
    return cfg


async def pause_agent(
    agent_slug: str,
    company_slug: str,
    reason: str,
    db: AsyncSession | None = None,
) -> None:
    async def _run(session: AsyncSession) -> None:
        company_id = await _get_company_id(company_slug, session)
        cfg = await _get_agent_config(agent_slug, company_id, session)
        if not hasattr(cfg, "is_paused"):
            raise GovernanceError("AgentConfig does not support is_paused. Run migration.")
        cfg.is_paused = True  # type: ignore[assignment]
        cfg.updated_at = datetime.now(timezone.utc)
        await audit_log.write_raw(
            company_id=company_slug,
            agent_slug="governance",
            action="agent.paused",
            payload={"agent": agent_slug, "reason": reason},
        )
        await session.commit()

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def resume_agent(
    agent_slug: str,
    company_slug: str,
    db: AsyncSession | None = None,
) -> None:
    async def _run(session: AsyncSession) -> None:
        company_id = await _get_company_id(company_slug, session)
        cfg = await _get_agent_config(agent_slug, company_id, session)
        cfg.is_paused = False  # type: ignore[assignment]
        cfg.updated_at = datetime.now(timezone.utc)
        await audit_log.write_raw(
            company_id=company_slug,
            agent_slug="governance",
            action="agent.resumed",
            payload={"agent": agent_slug},
        )
        await session.commit()

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def pause_all(company_slug: str, db: AsyncSession | None = None) -> None:
    async def _run(session: AsyncSession) -> None:
        company_id = await _get_company_id(company_slug, session)
        result = await session.execute(
            select(AgentConfig).where(AgentConfig.company_id == company_id)
        )
        configs = list(result.scalars().all())
        for cfg in configs:
            if hasattr(cfg, "is_paused"):
                cfg.is_paused = True  # type: ignore[assignment]
                cfg.updated_at = datetime.now(timezone.utc)
                await audit_log.write_raw(
                    company_id=company_slug,
                    agent_slug="governance",
                    action="agent.paused",
                    payload={"agent": cfg.agent_slug, "reason": "pause_all"},
                )
        await session.commit()

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def override(
    agent_slug: str,
    company_slug: str,
    reason: str,
    db: AsyncSession | None = None,
) -> None:
    await audit_log.write_raw(
        company_id=company_slug,
        agent_slug="governance",
        action="agent.overridden",
        payload={"agent": agent_slug, "reason": reason},
    )


async def rollback(
    audit_entry_id: str,
    reason: str,
    db: AsyncSession | None = None,
) -> None:
    async def _run(session: AsyncSession) -> None:
        eid = uuid.UUID(audit_entry_id)
        result = await session.execute(select(AuditEntry).where(AuditEntry.id == eid))
        entry = result.scalar_one_or_none()
        if entry is None:
            raise GovernanceError(f"Audit entry '{audit_entry_id}' not found.")
        if hasattr(entry, "is_rolled_back") and entry.is_rolled_back:  # type: ignore[union-attr]
            raise ImmutableAuditError(audit_entry_id)
        if hasattr(entry, "is_rolled_back"):
            entry.is_rolled_back = True  # type: ignore[assignment]
        # Write new audit entry recording rollback (never modify original)
        company_result = await session.execute(
            select(Company.slug).where(Company.id == entry.company_id)
        )
        company_slug = company_result.scalar_one_or_none() or str(entry.company_id)
        await audit_log.write_raw(
            company_id=company_slug,
            agent_slug="governance",
            action="audit.rollback",
            payload={"rolled_back_entry_id": audit_entry_id, "reason": reason},
        )
        await session.commit()

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def approve_specialist_hire(hire_id: str, approved_by: str) -> None:
    from src.agents.hiring_manager import approve_hire
    await approve_hire(hire_id=hire_id, approved_by=approved_by)
