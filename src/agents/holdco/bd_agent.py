"""
src/agents/holdco/bd_agent.py  (AM-53)

BD (Business Development) agent — new brand scouting and acquisition analysis.
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
    "You are the Business Development agent for a house of D2C brands. "
    "You scout potential acquisition targets, evaluate brand fit, "
    "assess market opportunity, and prepare investment memos. "
    "Focus on Indian D2C brands in personal care, food & beverage, and fashion."
)


class BDAgent(BaseAgent):
    def __init__(self, agent_id: str = "holdco-bd", company_id: str = "holdco") -> None:
        super().__init__(agent_id=agent_id, company_id=company_id, task_type="strategy")

    def get_tools(self) -> list[str]:
        return ["supabase_client", "d2c_benchmarks", "ticket_system", "audit_log"]

    async def run(self, task: AgentTask) -> AgentResult:
        if self.is_paused:
            raise AgentPausedError(self.agent_id)

        await audit_log.write_raw(
            company_id=self.company_id, agent_slug=self.agent_id,
            action="bd.run.start", payload={"task_subtype": task.task_subtype},
        )

        messages = [LLMMessage(role="user", content=_build_prompt(task))]
        llm_response = await provider.call(
            task_type=self.task_type,
            messages=[m.model_dump() for m in messages],
            agent_id=self.agent_id, company_id=self.company_id,
        )

        ticket_id = await ticket_system.create_ticket(
            company_slug=self.company_id, agent_slug=self.agent_id,
            summary=f"BD: {task.task_subtype}", description=llm_response.content,
            task_type=task.task_subtype,
        )

        await audit_log.write_raw(
            company_id=self.company_id, agent_slug=self.agent_id,
            action="bd.run.complete",
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
    if subtype == "scout_brands":
        return f"Scout potential D2C brand acquisitions in these categories. Context: {ctx}"
    elif subtype == "evaluate_target":
        return f"Evaluate this brand as an acquisition target. Context: {ctx}"
    elif subtype == "investment_memo":
        return f"Prepare an investment memo for this brand. Context: {ctx}"
    return f"BD task: {subtype}. Context: {ctx}"
