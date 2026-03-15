"""
src/agents/templates/ops.py  (AM-51)

Ops agent: supplier follow-ups, 3PL coordination, FSSAI calendar.
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
    "You are the Operations Manager agent for an Indian D2C brand. "
    "You manage supplier relationships, coordinate with 3PL partners (Shiprocket, Delhivery), "
    "track FSSAI compliance deadlines, and ensure inventory levels meet demand forecasts. "
    "Flag any supply chain risks proactively."
)


class OpsAgent(BaseAgent):
    def __init__(self, agent_id: str = "aim-ops", company_id: str = "aim") -> None:
        super().__init__(agent_id=agent_id, company_id=company_id, task_type="batch")

    def get_tools(self) -> list[str]:
        return ["shiprocket", "delhivery", "fssai", "gmail", "shopify", "ticket_system", "audit_log"]

    async def run(self, task: AgentTask) -> AgentResult:
        if self.is_paused:
            raise AgentPausedError(self.agent_id)

        await audit_log.write_raw(
            company_id=self.company_id, agent_slug=self.agent_id,
            action="ops.run.start", payload={"task_subtype": task.task_subtype},
        )

        messages = [LLMMessage(role="user", content=_build_prompt(task))]
        llm_response = await provider.call(
            task_type=self.task_type,
            messages=[m.model_dump() for m in messages],
            agent_id=self.agent_id, company_id=self.company_id,
        )

        ticket_id = await ticket_system.create_ticket(
            company_slug=self.company_id, agent_slug=self.agent_id,
            summary=f"Ops: {task.task_subtype}", description=llm_response.content,
            task_type=task.task_subtype,
        )

        await audit_log.write_raw(
            company_id=self.company_id, agent_slug=self.agent_id,
            action="ops.run.complete",
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
    if subtype == "supplier_followup":
        return f"Follow up with suppliers on pending orders and deliveries. Context: {ctx}"
    elif subtype == "inventory_check":
        return f"Check inventory levels across all channels and flag low-stock SKUs. Context: {ctx}"
    elif subtype == "compliance_check":
        return f"Check FSSAI compliance deadlines and upcoming audits. Context: {ctx}"
    elif subtype == "logistics_status":
        return f"Review 3PL performance and delivery SLA compliance. Context: {ctx}"
    return f"Ops task: {subtype}. Context: {ctx}"
