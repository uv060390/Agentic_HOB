"""
src/agents/templates/scout.py  (AM-47)

Scout agent: Meta Ad Library scraping, Reddit monitoring, competitor intelligence.
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
    "You are the Scout agent for an Indian D2C brand. Your role is to monitor "
    "competitors via Meta Ad Library, track Reddit discussions about the category, "
    "and flag emerging trends. Report actionable intelligence, not noise."
)


class ScoutAgent(BaseAgent):
    def __init__(self, agent_id: str = "aim-scout", company_id: str = "aim") -> None:
        super().__init__(agent_id=agent_id, company_id=company_id, task_type="batch")

    def get_tools(self) -> list[str]:
        return ["meta_ads", "supabase_client", "ticket_system", "audit_log", "google_drive"]

    async def run(self, task: AgentTask) -> AgentResult:
        if self.is_paused:
            raise AgentPausedError(self.agent_id)

        await audit_log.write_raw(
            company_id=self.company_id, agent_slug=self.agent_id,
            action="scout.run.start", payload={"task_subtype": task.task_subtype},
        )

        messages = [LLMMessage(role="user", content=_build_prompt(task))]
        llm_response = await provider.call(
            task_type=self.task_type,
            messages=[m.model_dump() for m in messages],
            agent_id=self.agent_id, company_id=self.company_id,
        )

        ticket_id = await ticket_system.create_ticket(
            company_slug=self.company_id, agent_slug=self.agent_id,
            summary=f"Scout: {task.task_subtype}", description=llm_response.content,
            task_type=task.task_subtype,
        )

        await audit_log.write_raw(
            company_id=self.company_id, agent_slug=self.agent_id,
            action="scout.run.complete",
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
    if subtype == "competitor_scan":
        return f"Scan Meta Ad Library for competitor ads in our category. Context: {ctx}"
    elif subtype == "reddit_monitor":
        return f"Monitor Reddit for brand mentions and category trends. Context: {ctx}"
    elif subtype == "trend_alert":
        return f"Identify emerging trends from recent competitor activity. Context: {ctx}"
    return f"Scout task: {subtype}. Context: {ctx}"
