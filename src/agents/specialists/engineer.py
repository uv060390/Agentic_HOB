"""
src/agents/specialists/engineer.py  (AM-37)
"""
from __future__ import annotations
import logging
from src.agents.base_agent import BaseAgent
from src.shared.schemas import AgentTask, AgentResult, AgentReport, LLMMessage
from src.shared.exceptions import AgentWindDownError, AgentPausedError
from src.core import audit_log
from src.core import ticket_system
import src.llm.provider as provider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a Senior Backend Engineer specialising in ad tech pipelines and API integrations "
    "for Indian D2C companies. You design data pipelines, API integrations, and automation workflows. "
    "Provide concrete technical specs with implementation steps."
)


class EngineerAgent(BaseAgent):
    def __init__(self, agent_id: str, company_id: str, task_type: str = "batch") -> None:
        super().__init__(agent_id=agent_id, company_id=company_id, task_type=task_type)

    def get_tools(self) -> list[str]:
        return ["supabase_client", "ticket_system", "audit_log"]

    async def run(self, task: AgentTask) -> AgentResult:
        if self.wound_down_at is not None:
            raise AgentWindDownError(self.agent_id)
        if self.is_paused:
            raise AgentPausedError(self.agent_id)

        effective_task_type = task.context.get("override_task_type", self.task_type)

        await audit_log.write_raw(
            company_id=self.company_id,
            agent_slug=self.agent_id,
            action="engineer.run.start",
            payload={"task_subtype": task.task_subtype},
        )

        messages = [LLMMessage(role="user", content=_build_prompt(task))]
        llm_response = await provider.call(
            task_type=effective_task_type,
            messages=[m.model_dump() for m in messages],
            agent_id=self.agent_id,
            company_id=self.company_id,
        )

        ticket_id = await ticket_system.create_ticket(
            company_slug=self.company_id,
            agent_slug=self.agent_id,
            summary=f"Engineer: {task.task_subtype}",
            description=llm_response.content,
            task_type=task.task_subtype,
        )

        await audit_log.write_raw(
            company_id=self.company_id,
            agent_slug=self.agent_id,
            action="engineer.run.complete",
            payload={"task_subtype": task.task_subtype, "ticket_id": ticket_id},
            ticket_id=ticket_id,
        )

        self._mark_run()
        return AgentResult(success=True, output=llm_response.content, ticket_id=ticket_id)

    async def report(self) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            company_id=self.company_id,
            last_run_at=self._last_run_at,
            status=(
                "wound_down" if self.wound_down_at
                else ("paused" if self.is_paused else "active")
            ),
        )


def _build_prompt(task: AgentTask) -> str:
    subtype = task.task_subtype
    ctx = task.context
    if subtype == "build_pipeline":
        return f"Design a data pipeline spec for: {ctx}"
    elif subtype == "integrate_api":
        return f"Produce an integration plan for this API: {ctx}"
    elif subtype == "automate_process":
        return f"Design an automation workflow for: {ctx}"
    return f"Engineering task: {subtype}. Context: {ctx}"
