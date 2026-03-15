"""
src/agents/templates/cmo.py  (AM-48)

CMO agent: campaign briefs, creative direction, brand strategy.
"""

from __future__ import annotations

import logging

from src.agents.base_agent import BaseAgent
from src.core import audit_log, ticket_system
from src.shared.exceptions import AgentPausedError
from src.shared.schemas import AgentReport, AgentResult, AgentTask, LLMMessage
import src.llm.provider as provider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the Chief Marketing Officer agent for an Indian D2C brand. "
    "You set creative direction, write campaign briefs, allocate channel budgets, "
    "and ensure brand consistency across all touchpoints. "
    "Your decisions are data-informed — reference CAC, ROAS, and benchmark data."
)


class CMOAgent(BaseAgent):
    def __init__(self, agent_id: str = "aim-cmo", company_id: str = "aim") -> None:
        super().__init__(agent_id=agent_id, company_id=company_id, task_type="strategy")

    def get_tools(self) -> list[str]:
        return ["meta_ads", "google_ads", "d2c_benchmarks", "ticket_system", "audit_log"]

    async def run(self, task: AgentTask) -> AgentResult:
        if self.is_paused:
            raise AgentPausedError(self.agent_id)

        await audit_log.write_raw(
            company_id=self.company_id, agent_slug=self.agent_id,
            action="cmo.run.start", payload={"task_subtype": task.task_subtype},
        )

        messages = [LLMMessage(role="user", content=_build_prompt(task))]
        llm_response = await provider.call(
            task_type=self.task_type,
            messages=[m.model_dump() for m in messages],
            agent_id=self.agent_id, company_id=self.company_id,
        )

        ticket_id = await ticket_system.create_ticket(
            company_slug=self.company_id, agent_slug=self.agent_id,
            summary=f"CMO: {task.task_subtype}", description=llm_response.content,
            task_type=task.task_subtype,
        )

        await audit_log.write_raw(
            company_id=self.company_id, agent_slug=self.agent_id,
            action="cmo.run.complete",
            payload={"task_subtype": task.task_subtype, "ticket_id": ticket_id},
            ticket_id=ticket_id,
        )

        self._mark_run()
        return AgentResult(success=True, output=llm_response.content, ticket_id=ticket_id)

    async def report(self) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id, company_id=self.company_id,
            last_run_at=self._last_run_at, open_tickets_count=0,
            status="active" if not self.is_paused else "paused",
        )


def _build_prompt(task: AgentTask) -> str:
    subtype = task.task_subtype
    ctx = task.context
    if subtype == "campaign_brief":
        return f"Write a campaign brief for the next ad cycle. Context: {ctx}"
    elif subtype == "creative_direction":
        return f"Set creative direction for upcoming campaigns. Context: {ctx}"
    elif subtype == "channel_budget_allocation":
        return f"Allocate marketing budget across channels based on performance. Context: {ctx}"
    elif subtype == "brand_audit":
        return f"Conduct a brand health audit across channels. Context: {ctx}"
    return f"CMO task: {subtype}. Context: {ctx}"
