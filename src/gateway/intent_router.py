"""
src/gateway/intent_router.py  (AM-82, AM-83, AM-113)

Routes natural language messages → brand + agent + task resolution.
Checks needs_onboarding() before dispatching to the agent layer.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from src.shared.schemas import AgentResult, AgentTask

logger = logging.getLogger(__name__)

# Brand keyword → slug mapping
_BRAND_KEYWORDS: dict[str, str] = {
    "aim": "aim",
    "lembasmax": "lembasmax",
    "lembas": "lembasmax",
}

# Intent keyword → (agent_template, task_subtype) mapping
_INTENT_MAP: list[tuple[list[str], str, str]] = [
    (["how's", "status", "synthesis", "summary", "overview"], "ceo", "weekly_synthesis"),
    (["finance", "p&l", "pl", "unit economics", "budget", "cac", "ltv"], "finance", "unit_economics"),
    (["campaign", "brief", "marketing plan"], "cmo", "campaign_brief"),
    (["creative", "ad copy", "hooks", "variants"], "creative", "ad_copy"),
    (["performance", "roas", "ads", "spend", "bid"], "performance", "daily_performance_check"),
    (["scout", "competitor", "ad library"], "scout", "competitor_scan"),
    (["ops", "supplier", "inventory", "shipping", "fssai", "compliance"], "ops", "compliance_check"),
    (["seo", "aeo", "geo", "visibility", "chatgpt visibility"], "seo_aeo", "visibility_audit"),
    (["growth", "referral", "retention", "viral"], "growth_hacker", "referral_program"),
    (["portfolio", "consolidated", "all brands"], "portfolio_cfo", "consolidated_pl"),
    (["acquisition", "new brand", "scout brand"], "bd", "scout_brands"),
]


def resolve_intent(
    message: str,
    default_brand: str = "aim",
) -> dict[str, str]:
    """
    Parse a natural language message into brand_slug, agent_template, and task_subtype.

    Returns:
        {"brand_slug": ..., "agent_template": ..., "task_subtype": ...}
    """
    msg_lower = message.lower().strip()

    # Detect brand
    brand_slug = default_brand
    for keyword, slug in _BRAND_KEYWORDS.items():
        if keyword in msg_lower:
            brand_slug = slug
            break

    # Detect intent
    for keywords, agent_template, task_subtype in _INTENT_MAP:
        for kw in keywords:
            if kw in msg_lower:
                return {
                    "brand_slug": brand_slug,
                    "agent_template": agent_template,
                    "task_subtype": task_subtype,
                }

    # Default: route to CEO for general queries
    return {
        "brand_slug": brand_slug,
        "agent_template": "ceo",
        "task_subtype": "weekly_synthesis",
    }


async def dispatch(
    message: str,
    founder_id: str,
    channel: str = "whatsapp",
) -> AgentResult:
    """
    Full dispatch pipeline: onboarding check → intent resolution → agent execution.

    Args:
        message:    Raw message text from founder.
        founder_id: Founder identifier (phone number or telegram user ID).
        channel:    "whatsapp" | "telegram"

    Returns:
        AgentResult from the dispatched agent.
    """
    # Step 1: Check if onboarding is needed (AM-113)
    try:
        from src.gateway.routes.onboarding import needs_onboarding, handle_onboarding_message
        if await needs_onboarding(founder_id):
            logger.info("Routing to onboarding | founder=%s", founder_id)
            onboarding_response = await handle_onboarding_message(founder_id, message, channel)
            return AgentResult(
                success=True,
                output=onboarding_response,
                metadata={"routed_to": "onboarding"},
            )
    except ImportError:
        logger.warning("Onboarding module not available, skipping check")
    except Exception as exc:
        logger.error("Onboarding check failed: %s", exc)

    # Step 2: Resolve intent
    intent = resolve_intent(message)
    brand_slug = intent["brand_slug"]
    agent_template = intent["agent_template"]
    task_subtype = intent["task_subtype"]

    logger.info(
        "Intent resolved | brand=%s agent=%s task=%s",
        brand_slug, agent_template, task_subtype,
    )

    # Step 3: Get agent and execute
    from src.agents.registry import get_agent_instance

    agent = await get_agent_instance(agent_template, brand_slug)
    task = AgentTask(
        task_subtype=task_subtype,
        context={"message": message, "founder_id": founder_id, "channel": channel},
    )

    return await agent.run(task)
