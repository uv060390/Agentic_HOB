"""
src/core/budget_enforcer.py  (AM-19)

Token usage tracking and per-agent monthly hard limits.
- check(): raises BudgetExceededError if the agent has hit its monthly cap.
- record(): inserts a token_usage row and emits an audit alert at 80% usage.

Budget caps are read from agent_config.monthly_budget_cap_usd in the database.
Agents pass slugs; this module resolves UUIDs as needed.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from src.shared.db import get_db
from src.shared.exceptions import BudgetExceededError
from src.shared.models import AgentConfig, Company, TokenUsage

logger = logging.getLogger(__name__)


async def _resolve_ids(agent_slug: str, company_slug: str) -> tuple[uuid.UUID, uuid.UUID, float | None]:
    """
    Resolve (agent_config_uuid, company_uuid, budget_cap) from slugs.
    Returns budget_cap=None if agent not found (uncapped / new agent).
    """
    async with get_db() as session:
        result = await session.execute(
            select(AgentConfig.id, AgentConfig.monthly_budget_cap_usd, Company.id)
            .join(Company, AgentConfig.company_id == Company.id)
            .where(
                AgentConfig.agent_slug == agent_slug,
                Company.slug == company_slug,
            )
        )
        row = result.first()
        if row is None:
            # Agent not yet seeded — skip enforcement
            return uuid.uuid4(), uuid.uuid4(), None
        agent_uuid, cap, company_uuid = row
        return agent_uuid, company_uuid, float(cap) if cap is not None else None


async def _get_monthly_spent(agent_uuid: uuid.UUID) -> float:
    """Return total cost_usd spent by this agent UUID in the current calendar month."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    async with get_db() as session:
        result = await session.execute(
            select(func.coalesce(func.sum(TokenUsage.cost_usd), 0.0)).where(
                TokenUsage.agent_id == agent_uuid,
                TokenUsage.created_at >= month_start,
            )
        )
        return float(result.scalar_one())


async def check(agent_id: str, company_id: str) -> None:
    """
    Pre-call budget guard. Raises BudgetExceededError if the monthly cap is hit.

    Args:
        agent_id: Agent slug (e.g. "aim-ceo").
        company_id: Brand slug (e.g. "aim").

    Raises:
        BudgetExceededError: if spent >= cap.
    """
    agent_uuid, _company_uuid, cap = await _resolve_ids(agent_id, company_id)
    if cap is None:
        return  # No cap configured — allow

    spent = await _get_monthly_spent(agent_uuid)
    if spent >= cap:
        raise BudgetExceededError(
            agent_slug=agent_id,
            company_slug=company_id,
            cap_usd=cap,
        )

    # 80% alert
    if spent >= cap * 0.80:
        logger.warning(
            "Budget alert: agent '%s' for brand '%s' has used %.1f%% of monthly cap ($%.4f / $%.2f).",
            agent_id,
            company_id,
            (spent / cap) * 100,
            spent,
            cap,
        )


async def record(
    *,
    agent_id: str,
    company_id: str,
    model: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> None:
    """
    Persist a TokenUsage row after a successful LLM call.

    Args:
        agent_id: Agent slug.
        company_id: Brand slug.
        model: Model ID (e.g. "claude-opus-4-6").
        provider: Provider name (e.g. "anthropic").
        input_tokens: Prompt tokens consumed.
        output_tokens: Completion tokens generated.
        cost_usd: Computed cost in USD.
    """
    agent_uuid, company_uuid, _cap = await _resolve_ids(agent_id, company_id)

    async with get_db() as session:
        usage = TokenUsage(
            agent_id=agent_uuid,
            company_id=company_uuid,
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )
        session.add(usage)
