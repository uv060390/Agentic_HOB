#!/usr/bin/env python3
"""
scripts/seed_agents.py  (AM-40)

Seeds AIM CEO and Finance agent configs into agent_config table.
Requires AIM company to already be seeded (run seed_companies.py first).
Idempotent: safe to run multiple times.
"""
import asyncio
import os
import sys
import uuid

from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.db import get_db
from src.shared.models import Company, AgentConfig


_AGENTS = [
    {
        "agent_slug": "aim-ceo",
        "agent_template": "ceo",
        "agent_type": "standing",
        "model_tier": "strategy",
        "monthly_budget_cap_usd": 50.0,
        "is_specialist": False,
        "is_paused": False,
        "reports_to_slug": None,
        "is_active": True,
    },
    {
        "agent_slug": "aim-finance",
        "agent_template": "finance",
        "agent_type": "standing",
        "model_tier": "strategy",
        "monthly_budget_cap_usd": 30.0,
        "is_specialist": False,
        "is_paused": False,
        "reports_to_slug": "aim-ceo",
        "is_active": True,
    },
]


async def main() -> None:
    db_url = os.environ.get("BRANDOS_DB_URL")
    if not db_url:
        print("ERROR: BRANDOS_DB_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    async with get_db() as session:
        result = await session.execute(select(Company).where(Company.slug == "aim"))
        aim = result.scalar_one_or_none()
        if aim is None:
            print("ERROR: AIM company not found. Run seed_companies.py first.", file=sys.stderr)
            sys.exit(1)

        inserted = 0
        skipped = 0
        for agent_data in _AGENTS:
            existing = await session.execute(
                select(AgentConfig).where(
                    AgentConfig.agent_slug == agent_data["agent_slug"],
                    AgentConfig.company_id == aim.id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                print(f"  SKIP  {agent_data['agent_slug']} (already exists)")
                skipped += 1
                continue

            cfg = AgentConfig(
                id=uuid.uuid4(),
                company_id=aim.id,
                **{k: v for k, v in agent_data.items() if hasattr(AgentConfig, k)},
            )
            session.add(cfg)
            print(f"  INSERT {agent_data['agent_slug']}")
            inserted += 1

        await session.commit()
        print(f"\nDone. {inserted} inserted, {skipped} skipped.")


if __name__ == "__main__":
    asyncio.run(main())
