"""
src/agents/base_agent.py  (AM-27)

Abstract base class for all BrandOS agents.
"""
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from src.shared.schemas import AgentTask, AgentResult, AgentReport

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    def __init__(self, agent_id: str, company_id: str, task_type: str) -> None:
        self.agent_id = agent_id
        self.company_id = company_id
        self.task_type = task_type
        self._last_run_at: str | None = None
        self.wound_down_at: datetime | None = None
        self.is_paused: bool = False

    @abstractmethod
    async def run(self, task: AgentTask) -> AgentResult:
        """Execute the task. Must write audit log entries."""
        ...

    @abstractmethod
    async def report(self) -> AgentReport:
        """Return current status summary."""
        ...

    @abstractmethod
    def get_tools(self) -> list[str]:
        """Return list of tool slugs this agent is permitted to use."""
        ...

    def _mark_run(self) -> None:
        self._last_run_at = datetime.now(timezone.utc).isoformat()

    async def delegate(
        self,
        task_subtype: str,
        target_agent_template: str,
        context: dict[str, Any] | None = None,
    ) -> "AgentResult":
        """
        Delegate a sub-task to another agent.

        Agents must never call each other directly — always use delegate().
        Brand isolation is preserved: company_id is always self.company_id.
        The delegated agent writes its own audit entries.
        """
        from src.agents.registry import get_agent_instance  # avoid circular import

        agent = await get_agent_instance(target_agent_template, self.company_id)
        task = AgentTask(
            task_subtype=task_subtype,
            context=context or {},
        )
        return await agent.run(task)
