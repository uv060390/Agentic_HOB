"""
src/agents/specialists/data_scientist.py  (AM-36)
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
    "You are a Senior Data Scientist specialising in Indian D2C performance marketing. "
    "You build ML models for CAC optimisation, LTV prediction, and bid strategy. "
    "Provide actionable, quantified recommendations. Reference specific cohorts and channels."
)


class DataScientistAgent(BaseAgent):
    def __init__(self, agent_id: str, company_id: str) -> None:
        super().__init__(agent_id=agent_id, company_id=company_id, task_type="strategy")
        self._tasks_completed: int = 0
        self._budget_allocated: float = 0.0
        self._budget_spent: float = 0.0

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
            action="data_scientist.run.start",
            payload={"task_subtype": task.task_subtype},
        )

        messages = [LLMMessage(role="user", content=_build_prompt(task))]
        llm_response = await provider.call(
            task_type=self.task_type,
            messages=[m.model_dump() for m in messages],
            agent_id=self.agent_id,
            company_id=self.company_id,
        )
        self._budget_spent += llm_response.cost_usd
        self._tasks_completed += 1

        ticket_id = await ticket_system.create_ticket(
            company_slug=self.company_id,
            agent_slug=self.agent_id,
            summary=f"DataScientist: {task.task_subtype}",
            description=llm_response.content,
            task_type=task.task_subtype,
        )

        await audit_log.write_raw(
            company_id=self.company_id,
            agent_slug=self.agent_id,
            action="data_scientist.run.complete",
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
            open_tickets_count=self._tasks_completed,
            status=(
                "wound_down" if self.wound_down_at
                else ("paused" if self.is_paused else "active")
            ),
        )


def _build_prompt(task: AgentTask) -> str:
    subtype = task.task_subtype
    ctx = task.context
    if subtype == "analyse_cac":
        return f"Analyse CAC trends and identify wasted spend segments. Data: {ctx}"
    elif subtype == "predict_ltv":
        return f"Build LTV cohort model from order history. Data: {ctx}"
    elif subtype == "optimise_bids":
        return f"Recommend bid strategy changes based on ROAS data. Data: {ctx}"
    return f"Data science task: {subtype}. Context: {ctx}"
