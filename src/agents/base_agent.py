"""
src/agents/base_agent.py  (AM-27)

Abstract base class for all BrandOS agents.
"""
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
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
