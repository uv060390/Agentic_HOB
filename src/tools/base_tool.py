"""
src/tools/base_tool.py  (AM-56)

Abstract base class for all BrandOS tool wrappers.
Tools are organised by domain and activated per brand based on need and budget.
All tool calls are scoped to a single brand — cross-brand access is forbidden.
Credentials are fetched from Infisical at runtime, never stored in code.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """
    Abstract base class for all tool wrappers.

    Subclasses must implement:
      - slug:     class-level string identifying the tool (e.g. "meta_ads")
      - execute:  async method that performs the tool action
    """

    slug: str = ""

    def __init__(self, company_slug: str) -> None:
        self.company_slug = company_slug

    @abstractmethod
    async def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a tool action.

        Args:
            action: The specific operation to perform (e.g. "get_campaigns").
            params: Parameters for the operation.

        Returns:
            Result dict with at minimum {"ok": bool, "data": ...}.

        Raises:
            ToolExecutionError: if the external API call fails.
        """
        ...

    def _log_call(self, action: str, params: dict[str, Any]) -> None:
        logger.info(
            "Tool.%s | brand=%s action=%s params=%s",
            self.slug, self.company_slug, action, list(params.keys()),
        )
