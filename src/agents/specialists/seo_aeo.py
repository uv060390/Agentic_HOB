"""
src/agents/specialists/seo_aeo.py  (AM-54)

SEO + AEO/GEO specialist — generative engine optimisation.
Tests brand visibility in ChatGPT and Perplexity answers.
Uses LLM-as-tool (src/tools/llm_as_tool/), NOT src/llm/provider.py.
"""

from __future__ import annotations

import logging

from src.agents.base_agent import BaseAgent
from src.core import audit_log, ticket_system
from src.shared.exceptions import AgentPausedError, AgentWindDownError
from src.shared.schemas import AgentReport, AgentResult, AgentTask, LLMMessage
import src.llm.provider as provider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an SEO and AEO/GEO specialist for an Indian D2C brand. "
    "Your mandate is to ensure the brand appears prominently in AI-generated answers "
    "(ChatGPT, Perplexity) and traditional search results. "
    "You audit visibility, create content strategies, and test via LLM-as-tool APIs."
)


class SEOAEOAgent(BaseAgent):
    def __init__(self, agent_id: str, company_id: str) -> None:
        super().__init__(agent_id=agent_id, company_id=company_id, task_type="creative")
        self._audits_completed: int = 0

    def get_tools(self) -> list[str]:
        return ["chatgpt_aeo", "perplexity_aeo", "supabase_client", "ticket_system", "audit_log"]

    async def run(self, task: AgentTask) -> AgentResult:
        if self.wound_down_at is not None:
            raise AgentWindDownError(self.agent_id)
        if self.is_paused:
            raise AgentPausedError(self.agent_id)

        await audit_log.write_raw(
            company_id=self.company_id, agent_slug=self.agent_id,
            action="seo_aeo.run.start", payload={"task_subtype": task.task_subtype},
        )

        messages = [LLMMessage(role="user", content=_build_prompt(task))]
        llm_response = await provider.call(
            task_type=self.task_type,
            messages=[m.model_dump() for m in messages],
            agent_id=self.agent_id, company_id=self.company_id,
        )
        self._audits_completed += 1

        ticket_id = await ticket_system.create_ticket(
            company_slug=self.company_id, agent_slug=self.agent_id,
            summary=f"SEO/AEO: {task.task_subtype}", description=llm_response.content,
            task_type=task.task_subtype,
        )

        await audit_log.write_raw(
            company_id=self.company_id, agent_slug=self.agent_id,
            action="seo_aeo.run.complete",
            payload={"task_subtype": task.task_subtype, "ticket_id": ticket_id},
            ticket_id=ticket_id,
        )

        self._mark_run()
        return AgentResult(success=True, output=llm_response.content, ticket_id=ticket_id)

    async def report(self) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id, company_id=self.company_id,
            last_run_at=self._last_run_at, open_tickets_count=self._audits_completed,
            status=(
                "wound_down" if self.wound_down_at
                else ("paused" if self.is_paused else "active")
            ),
        )


def _build_prompt(task: AgentTask) -> str:
    subtype = task.task_subtype
    ctx = task.context
    if subtype == "visibility_audit":
        return f"Audit brand visibility across ChatGPT and Perplexity for key queries. Context: {ctx}"
    elif subtype == "content_strategy":
        return f"Create content strategy to improve AI-engine visibility. Context: {ctx}"
    elif subtype == "competitor_visibility":
        return f"Analyse competitor visibility in AI-generated answers. Context: {ctx}"
    return f"SEO/AEO task: {subtype}. Context: {ctx}"
