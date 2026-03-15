"""
src/agents/holdco/portfolio_cfo.py  (AM-52)

Cross-brand Portfolio CFO — consolidated P&L across all brands.
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
    "You are the Portfolio CFO for a house of D2C brands. "
    "You consolidate P&L across all brands, identify cross-brand synergies, "
    "flag underperforming brands, and recommend capital allocation. "
    "Be rigorous with numbers and flag any brand that is burning cash without clear ROI."
)


class PortfolioCFOAgent(BaseAgent):
    def __init__(self, agent_id: str = "holdco-cfo", company_id: str = "holdco") -> None:
        super().__init__(agent_id=agent_id, company_id=company_id, task_type="strategy")

    def get_tools(self) -> list[str]:
        return ["supabase_client", "ticket_system", "audit_log"]

    async def run(self, task: AgentTask) -> AgentResult:
        if self.is_paused:
            raise AgentPausedError(self.agent_id)

        await audit_log.write_raw(
            company_id=self.company_id, agent_slug=self.agent_id,
            action="portfolio_cfo.run.start", payload={"task_subtype": task.task_subtype},
        )

        messages = [LLMMessage(role="user", content=_build_prompt(task))]
        llm_response = await provider.call(
            task_type=self.task_type,
            messages=[m.model_dump() for m in messages],
            agent_id=self.agent_id, company_id=self.company_id,
        )

        ticket_id = await ticket_system.create_ticket(
            company_slug=self.company_id, agent_slug=self.agent_id,
            summary=f"PortfolioCFO: {task.task_subtype}", description=llm_response.content,
            task_type=task.task_subtype,
        )

        await audit_log.write_raw(
            company_id=self.company_id, agent_slug=self.agent_id,
            action="portfolio_cfo.run.complete",
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
    if subtype == "consolidated_pl":
        return f"Consolidate P&L across all brands. Data: {ctx}"
    elif subtype == "capital_allocation":
        return f"Recommend capital allocation across brands. Data: {ctx}"
    elif subtype == "brand_health_comparison":
        return f"Compare brand health metrics across the portfolio. Data: {ctx}"
    return f"PortfolioCFO task: {subtype}. Data: {ctx}"
