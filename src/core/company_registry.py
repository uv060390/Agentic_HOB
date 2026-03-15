"""
src/core/company_registry.py  (AM-28)
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.db import get_db
from src.shared.models import Company
from src.shared.exceptions import CompanyNotFoundError


async def get_company(slug: str, db: AsyncSession | None = None) -> Company:
    async def _run(session: AsyncSession) -> Company:
        result = await session.execute(select(Company).where(Company.slug == slug))
        company = result.scalar_one_or_none()
        if company is None:
            raise CompanyNotFoundError(slug)
        return company

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def list_companies(db: AsyncSession | None = None) -> list[Company]:
    async def _run(session: AsyncSession) -> list[Company]:
        result = await session.execute(select(Company))
        return list(result.scalars().all())

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def get_active_companies(db: AsyncSession | None = None) -> list[Company]:
    async def _run(session: AsyncSession) -> list[Company]:
        result = await session.execute(
            select(Company).where(Company.is_active == True, Company.is_wind_down == False)
        )
        return list(result.scalars().all())

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def create_company(
    name: str,
    slug: str,
    mission: str | None = None,
    is_active: bool = True,
    is_wind_down: bool = False,
    db: AsyncSession | None = None,
) -> Company:
    async def _run(session: AsyncSession) -> Company:
        company = Company(
            id=uuid.uuid4(),
            slug=slug,
            name=name,
            mission=mission,
            is_active=is_active,
            is_wind_down=is_wind_down,
        )
        session.add(company)
        await session.commit()
        await session.refresh(company)
        return company

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)


async def update_company(slug: str, db: AsyncSession | None = None, **fields: Any) -> Company:
    async def _run(session: AsyncSession) -> Company:
        result = await session.execute(select(Company).where(Company.slug == slug))
        company = result.scalar_one_or_none()
        if company is None:
            raise CompanyNotFoundError(slug)
        for key, val in fields.items():
            if hasattr(company, key):
                setattr(company, key, val)
        company.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(company)
        return company

    if db is not None:
        return await _run(db)
    async with get_db() as session:
        return await _run(session)
