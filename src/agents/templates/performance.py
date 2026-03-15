"""
src/agents/templates/performance.py  (AM-50)

Performance agent: Meta/Google Ads API, bid management, CTR feedback loop.
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
    "You are the Performance Marketing agent for an Indian D2C brand. "
    "You manage Meta and Google ad campaigns, optimise bids, monitor ROAS, "
    "and flag anomalies (CAC spikes, CTR drops, budget pacing issues). "
    "You also update actual CTR in the Creative Library after each campaign flight."
)


class PerformanceAgent(BaseAgent):
    def __init__(self, agent_id: str = "aim-performance", company_id: str = "aim") -> None:
        super().__init__(agent_id=agent_id, company_id=company_id, task_type="batch")

    def get_tools(self) -> list[str]:
        return ["meta_ads", "google_ads", "google_drive", "d2c_benchmarks", "ticket_system", "audit_log"]

    async def run(self, task: AgentTask) -> AgentResult:
        if self.is_paused:
            raise AgentPausedError(self.agent_id)

        await audit_log.write_raw(
            company_id=self.company_id, agent_slug=self.agent_id,
            action="performance.run.start", payload={"task_subtype": task.task_subtype},
        )

        messages = [LLMMessage(role="user", content=_build_prompt(task))]
        llm_response = await provider.call(
            task_type=self.task_type,
            messages=[m.model_dump() for m in messages],
            agent_id=self.agent_id, company_id=self.company_id,
        )

        ticket_id = await ticket_system.create_ticket(
            company_slug=self.company_id, agent_slug=self.agent_id,
            summary=f"Performance: {task.task_subtype}", description=llm_response.content,
            task_type=task.task_subtype,
        )

        await audit_log.write_raw(
            company_id=self.company_id, agent_slug=self.agent_id,
            action="performance.run.complete",
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
    if subtype == "daily_performance_check":
        return f"Run daily performance check across all active campaigns. Context: {ctx}"
    elif subtype == "bid_optimisation":
        return f"Analyse bid performance and recommend changes. Context: {ctx}"
    elif subtype == "anomaly_alert":
        return f"Investigate this performance anomaly. Context: {ctx}"
    elif subtype == "roas_report":
        return f"Generate ROAS report by channel and campaign. Context: {ctx}"
    return f"Performance task: {subtype}. Context: {ctx}"
