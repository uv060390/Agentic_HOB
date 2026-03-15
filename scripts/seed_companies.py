"""
scripts/seed_companies.py

Seeds initial company records into the BrandOS database:
  - AIM       (active brand)
  - LembasMax (wind-down brand)

Usage:
    BRANDOS_DB_URL=postgresql+psycopg://... python scripts/seed_companies.py
"""

from __future__ import annotations

import asyncio
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.shared.models import Company


async def seed() -> None:
    db_url = os.environ["BRANDOS_DB_URL"]
    engine = create_async_engine(db_url, echo=True)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    companies = [
        Company(
            slug="aim",
            name="AIM",
            is_active=True,
            is_wind_down=False,
            mission=(
                "Build the leading science-backed cognitive nutrition brand in India, "
                "distributed D2C and across modern trade."
            ),
        ),
        Company(
            slug="lembasmax",
            name="LembasMax",
            is_active=True,
            is_wind_down=True,
            mission="Wind down operations: clear inventory, settle suppliers, delist channels.",
        ),
    ]

    async with async_session() as session:
        for company in companies:
            session.add(company)
        await session.commit()
        print(f"Seeded {len(companies)} companies.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
