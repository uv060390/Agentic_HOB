"""
src/agents/templates/ceo.py  (AM-32)
"""
from __future__ import annotations
import logging
from src.agents.base_agent import BaseAgent
from src.shared.schemas import AgentTask, AgentResult, AgentReport, AuditEntryCreate, LLMMessage
from src.shared.exceptions import AgentPausedError
from src.core import audit_log
from src.core import ticket_system
import src.llm.provider as provider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the CEO agent for a D2C brand. Your role is to synthesise weekly company status, "
    "check goal alignment, and escalate issues that require founder attention. "
    "You have access to the org chart, open tickets, and the company mission. "
    "Be concise, data-driven, and flag anomalies proactively."
)


class CEOAgent(BaseAgent):
    def __init__(self, agent_id: str = "aim-ceo", company_id: str = "aim") -> None:
        super().__init__(agent_id=agent_id, company_id=company_id, task_type="strategy")

    def get_tools(self) -> list[str]:
        return ["ticket_system", "org_chart", "goal_ancestry", "audit_log"]

    async def run(self, task: AgentTask) -> AgentResult:
        if self.is_paused:
            raise AgentPausedError(self.agent_id)

        await audit_log.write_raw(
            company_id=self.company_id,
            agent_slug=self.agent_id,
            action="ceo.run.start",
            payload={"task_subtype": task.task_subtype},
        )

        messages = [
            LLMMessage(role="user", content=_build_prompt(task)),
        ]

        llm_response = await provider.call(
            task_type=self.task_type,
            messages=[m.model_dump() for m in messages],
            agent_id=self.agent_id,
            company_id=self.company_id,
        )

        ticket_id = await ticket_system.create_ticket(
            company_slug=self.company_id,
            agent_slug=self.agent_id,
            summary=f"CEO: {task.task_subtype}",
            description=llm_response.content,
            task_type=task.task_subtype,
        )

        await audit_log.write_raw(
            company_id=self.company_id,
            agent_slug=self.agent_id,
            action="ceo.run.complete",
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
            open_tickets_count=0,
            status="active" if not self.is_paused else "paused",
        )


def _build_prompt(task: AgentTask) -> str:
    subtype = task.task_subtype
    ctx = task.context
    if subtype == "weekly_synthesis":
        return f"Synthesise the current company status. Context: {ctx}"
    elif subtype == "goal_alignment_check":
        return f"Check whether open tickets align with the company mission. Context: {ctx}"
    elif subtype == "escalate":
        return f"Prepare an escalation for founder review. Context: {ctx}"
    return f"Task: {subtype}. Context: {ctx}"
