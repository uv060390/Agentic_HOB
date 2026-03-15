"""
src/core/heartbeat.py  (AM-46)

APScheduler integration — cron-style schedule per agent.
Heartbeats trigger agents to run their routine tasks autonomously.
All heartbeats run server-side; never dependent on founder's machine.

IMPORTANT: Heartbeat checks use Llama 3.1 8B via Cerebras (monitoring task type).
Never waste premium model tokens on a heartbeat.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.db import get_db
from src.shared.models import AgentConfig, Company
from src.shared.schemas import AgentTask

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the global APScheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


async def _run_agent_heartbeat(agent_slug: str, company_slug: str, task_subtype: str) -> None:
    """Execute a single heartbeat for an agent."""
    from src.agents.registry import get_agent_instance

    logger.info(
        "Heartbeat firing | agent=%s brand=%s task=%s",
        agent_slug, company_slug, task_subtype,
    )

    try:
        agent = await get_agent_instance(agent_slug, company_slug)
        if agent.is_paused:
            logger.info("Heartbeat skipped — agent %s is paused", agent_slug)
            return

        task = AgentTask(task_subtype=task_subtype, context={"trigger": "heartbeat"})
        result = await agent.run(task)

        logger.info(
            "Heartbeat complete | agent=%s brand=%s success=%s",
            agent_slug, company_slug, result.success,
        )
    except Exception as exc:
        logger.error(
            "Heartbeat failed | agent=%s brand=%s error=%s",
            agent_slug, company_slug, str(exc),
        )


async def register_heartbeats() -> int:
    """
    Load all agent configs with heartbeat_cron set and register them
    with the scheduler. Returns the number of heartbeats registered.
    """
    scheduler = get_scheduler()
    count = 0

    async with get_db() as session:
        result = await session.execute(
            select(AgentConfig, Company.slug).join(
                Company, AgentConfig.company_id == Company.id
            ).where(
                AgentConfig.is_active == True,
                AgentConfig.heartbeat_cron.isnot(None),
                AgentConfig.heartbeat_cron != "",
            )
        )
        rows = result.all()

        for agent_config, company_slug in rows:
            cron_expr = agent_config.heartbeat_cron
            agent_slug = agent_config.agent_slug
            # Default heartbeat task subtype based on agent template
            task_subtype = _default_heartbeat_task(agent_config.agent_template or agent_slug)

            try:
                trigger = CronTrigger.from_crontab(cron_expr)
                job_id = f"heartbeat_{company_slug}_{agent_slug}"

                scheduler.add_job(
                    _run_agent_heartbeat,
                    trigger=trigger,
                    args=[agent_slug, company_slug, task_subtype],
                    id=job_id,
                    replace_existing=True,
                    name=f"Heartbeat: {agent_slug} ({company_slug})",
                )
                count += 1
                logger.info(
                    "Heartbeat registered | agent=%s brand=%s cron=%s task=%s",
                    agent_slug, company_slug, cron_expr, task_subtype,
                )
            except Exception as exc:
                logger.error(
                    "Failed to register heartbeat | agent=%s cron=%s error=%s",
                    agent_slug, cron_expr, str(exc),
                )

    return count


def _default_heartbeat_task(agent_template: str) -> str:
    """Map agent template to its default heartbeat task subtype."""
    return {
        "ceo": "weekly_synthesis",
        "finance": "budget_status",
        "scout": "competitor_scan",
        "cmo": "brand_audit",
        "creative": "ad_copy",
        "performance": "daily_performance_check",
        "ops": "compliance_check",
        "portfolio_cfo": "consolidated_pl",
        "bd": "scout_brands",
    }.get(agent_template, "heartbeat_check")


async def start_scheduler() -> None:
    """Start the heartbeat scheduler."""
    scheduler = get_scheduler()
    count = await register_heartbeats()
    scheduler.start()
    logger.info("Heartbeat scheduler started with %d jobs", count)


async def stop_scheduler() -> None:
    """Gracefully stop the heartbeat scheduler."""
    scheduler = get_scheduler()
    scheduler.shutdown(wait=True)
    logger.info("Heartbeat scheduler stopped")


def list_jobs() -> list[dict[str, Any]]:
    """Return info about all registered heartbeat jobs."""
    scheduler = get_scheduler()
    return [
        {
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
        }
        for job in scheduler.get_jobs()
    ]
