"""
src/agents/templates/creative.py  (AM-49)

Creative agent: ad copy, hooks, variants. Saves all output to Creative Library.
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
    "You are the Creative Director agent for an Indian D2C brand. "
    "You write ad copy, design hooks, create variants, and replicate top-performing "
    "competitor ads with brand-specific assets. All output must be saved to the "
    "Creative Library. Focus on high-CTR hooks and clear value propositions."
)


class CreativeAgent(BaseAgent):
    def __init__(self, agent_id: str = "aim-creative", company_id: str = "aim") -> None:
        super().__init__(agent_id=agent_id, company_id=company_id, task_type="creative")

    def get_tools(self) -> list[str]:
        return ["google_drive", "supabase_client", "ticket_system", "audit_log"]

    async def run(self, task: AgentTask) -> AgentResult:
        if self.is_paused:
            raise AgentPausedError(self.agent_id)

        await audit_log.write_raw(
            company_id=self.company_id, agent_slug=self.agent_id,
            action="creative.run.start", payload={"task_subtype": task.task_subtype},
        )

        messages = [LLMMessage(role="user", content=_build_prompt(task))]
        llm_response = await provider.call(
            task_type=self.task_type,
            messages=[m.model_dump() for m in messages],
            agent_id=self.agent_id, company_id=self.company_id,
        )

        # Save creative output to Creative Library
        from src.tools.storage.google_drive import save_creative
        await save_creative(
            brand_slug=self.company_id,
            file_name=f"{task.task_subtype}_{self.agent_id}.md",
            content=llm_response.content,
            metadata={"source": "original", "creative_type": "copy"},
            created_by_agent=self.agent_id,
            workflow_run_id=task.context.get("workflow_run_id"),
        )

        ticket_id = await ticket_system.create_ticket(
            company_slug=self.company_id, agent_slug=self.agent_id,
            summary=f"Creative: {task.task_subtype}", description=llm_response.content,
            task_type=task.task_subtype,
        )

        await audit_log.write_raw(
            company_id=self.company_id, agent_slug=self.agent_id,
            action="creative.run.complete",
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
    if subtype == "ad_copy":
        return f"Write 3 variants of ad copy for this brief. Context: {ctx}"
    elif subtype == "hooks":
        return f"Generate 5 high-CTR hook lines for social ads. Context: {ctx}"
    elif subtype == "replicate_top_ads":
        return f"Replicate these top-performing competitor ads with our brand assets. Context: {ctx}"
    elif subtype == "creative_brief":
        return f"Create a detailed creative brief for the design team. Context: {ctx}"
    return f"Creative task: {subtype}. Context: {ctx}"
