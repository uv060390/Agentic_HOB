"""
src/agents/specialists/data_analyst.py  (AM-38)
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
    "You are a Senior Data Analyst specialising in Indian D2C e-commerce analytics. "
    "You perform cohort analysis, funnel diagnostics, and attribution analysis. "
    "Present findings with clear data tables and actionable next steps."
)


class DataAnalystAgent(BaseAgent):
    def __init__(self, agent_id: str, company_id: str) -> None:
        super().__init__(agent_id=agent_id, company_id=company_id, task_type="batch")

    def get_tools(self) -> list[str]:
        return ["supabase_client", "ticket_system", "audit_log"]

    async def run(self, task: AgentTask) -> AgentResult:
        if self.wound_down_at is not None:
            raise AgentWindDownError(self.agent_id)
        if self.is_paused:
            raise AgentPausedError(self.agent_id)

        await audit_log.write_raw(
            company_id=self.company_id,
            agent_slug=self.agent_id,
            action="data_analyst.run.start",
            payload={"task_subtype": task.task_subtype},
        )

        messages = [LLMMessage(role="user", content=_build_prompt(task))]
        llm_response = await provider.call(
            task_type=self.task_type,
            messages=[m.model_dump() for m in messages],
            agent_id=self.agent_id,
            company_id=self.company_id,
        )

        ticket_id = await ticket_system.create_ticket(
            company_slug=self.company_id,
            agent_slug=self.agent_id,
            summary=f"DataAnalyst: {task.task_subtype}",
            description=llm_response.content,
            task_type=task.task_subtype,
        )

        await audit_log.write_raw(
            company_id=self.company_id,
            agent_slug=self.agent_id,
            action="data_analyst.run.complete",
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
    if subtype == "analyse_cohort":
        return f"Perform cohort retention and LTV breakdown by acquisition channel. Data: {ctx}"
    elif subtype == "diagnose_funnel":
        return f"Identify drop-off points in the conversion funnel. Data: {ctx}"
    elif subtype == "attribution_analysis":
        return f"Run first/last/multi-touch attribution for ad spend. Data: {ctx}"
    return f"Analytics task: {subtype}. Context: {ctx}"
