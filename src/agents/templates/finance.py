"""
src/agents/templates/finance.py  (AM-33)
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
    "You are the Finance Director agent for a D2C brand. Your mandate is to track unit economics, "
    "flag cost anomalies, and produce clear P&L summaries. "
    "Key metrics: CAC (Customer Acquisition Cost), LTV (Lifetime Value), "
    "contribution margin, and payback period. "
    "Be precise with numbers. Flag anything outside normal ranges immediately."
)


class FinanceAgent(BaseAgent):
    def __init__(self, agent_id: str = "aim-finance", company_id: str = "aim") -> None:
        super().__init__(agent_id=agent_id, company_id=company_id, task_type="strategy")
        self._last_contribution_margin: float | None = None

    def get_tools(self) -> list[str]:
        return ["supabase_client", "ticket_system", "audit_log"]

    async def run(self, task: AgentTask) -> AgentResult:
        if self.is_paused:
            raise AgentPausedError(self.agent_id)

        await audit_log.write_raw(
            company_id=self.company_id,
            agent_slug=self.agent_id,
            action="finance.run.start",
            payload={"task_subtype": task.task_subtype},
        )

        financial_data = task.context.get("financial_data", {})
        messages = [
            LLMMessage(role="user", content=_build_prompt(task, financial_data)),
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
            summary=f"Finance: {task.task_subtype}",
            description=llm_response.content,
            task_type=task.task_subtype,
        )

        await audit_log.write_raw(
            company_id=self.company_id,
            agent_slug=self.agent_id,
            action="finance.run.complete",
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


def _build_prompt(task: AgentTask, financial_data: dict) -> str:
    subtype = task.task_subtype
    data_str = str(financial_data) if financial_data else "No financial data provided."
    if subtype == "unit_economics":
        return (
            f"Calculate unit economics from this data: {data_str}. "
            "Report CAC, LTV, contribution margin, payback period."
        )
    elif subtype == "pl_draft":
        return f"Draft a monthly P&L summary from: {data_str}."
    elif subtype == "budget_status":
        return f"Report budget status across all agents. Data: {data_str}."
    return f"Finance task: {subtype}. Data: {data_str}."
