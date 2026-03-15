"""
src/agents/specialists/growth_hacker.py  (AM-55)

Growth Hacker specialist — referral loops, viral mechanics, retention experiments.
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
    "You are a Growth Hacker specialist for an Indian D2C brand. "
    "You design referral programs, viral loops, retention experiments, "
    "and activation funnels. Focus on measurable experiments with clear success criteria. "
    "Every recommendation must include expected lift, test duration, and sample size."
)


class GrowthHackerAgent(BaseAgent):
    def __init__(self, agent_id: str, company_id: str) -> None:
        super().__init__(agent_id=agent_id, company_id=company_id, task_type="creative")
        self._experiments_designed: int = 0

    def get_tools(self) -> list[str]:
        return ["supabase_client", "shopify", "d2c_benchmarks", "ticket_system", "audit_log"]

    async def run(self, task: AgentTask) -> AgentResult:
        if self.wound_down_at is not None:
            raise AgentWindDownError(self.agent_id)
        if self.is_paused:
            raise AgentPausedError(self.agent_id)

        await audit_log.write_raw(
            company_id=self.company_id, agent_slug=self.agent_id,
            action="growth_hacker.run.start", payload={"task_subtype": task.task_subtype},
        )

        messages = [LLMMessage(role="user", content=_build_prompt(task))]
        llm_response = await provider.call(
            task_type=self.task_type,
            messages=[m.model_dump() for m in messages],
            agent_id=self.agent_id, company_id=self.company_id,
        )
        self._experiments_designed += 1

        ticket_id = await ticket_system.create_ticket(
            company_slug=self.company_id, agent_slug=self.agent_id,
            summary=f"GrowthHacker: {task.task_subtype}", description=llm_response.content,
            task_type=task.task_subtype,
        )

        await audit_log.write_raw(
            company_id=self.company_id, agent_slug=self.agent_id,
            action="growth_hacker.run.complete",
            payload={"task_subtype": task.task_subtype, "ticket_id": ticket_id},
            ticket_id=ticket_id,
        )

        self._mark_run()
        return AgentResult(success=True, output=llm_response.content, ticket_id=ticket_id)

    async def report(self) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id, company_id=self.company_id,
            last_run_at=self._last_run_at,
            open_tickets_count=self._experiments_designed,
            status=(
                "wound_down" if self.wound_down_at
                else ("paused" if self.is_paused else "active")
            ),
        )


def _build_prompt(task: AgentTask) -> str:
    subtype = task.task_subtype
    ctx = task.context
    if subtype == "referral_program":
        return f"Design a referral program for this brand. Context: {ctx}"
    elif subtype == "retention_experiment":
        return f"Design a retention experiment with clear success criteria. Context: {ctx}"
    elif subtype == "viral_loop":
        return f"Design a viral loop mechanism for product sharing. Context: {ctx}"
    elif subtype == "activation_funnel":
        return f"Optimise the activation funnel from signup to first purchase. Context: {ctx}"
    return f"GrowthHacker task: {subtype}. Context: {ctx}"
