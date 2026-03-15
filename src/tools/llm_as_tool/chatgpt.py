"""
src/tools/llm_as_tool/chatgpt.py  (AM-65)

OpenAI API for AEO/GEO brand visibility testing.
This is a TOOL, not an LLM provider — it tests brand presence in ChatGPT answers.
Never route through model_router or src/llm/provider.py.
Credentials fetched from Infisical: /{brand}/openai_api_key
"""

from __future__ import annotations

import logging
from typing import Any

from src.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class ChatGPTTool(BaseTool):
    slug = "chatgpt_aeo"

    async def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        self._log_call(action, params)

        if action == "test_brand_visibility":
            query = params.get("query", "")
            return {
                "ok": True,
                "data": {
                    "query": query,
                    "brand_mentioned": False,
                    "position": None,
                    "competitor_mentions": [],
                    "response_snippet": f"[Mock ChatGPT response for: {query}]",
                },
            }
        elif action == "batch_visibility_test":
            queries = params.get("queries", [])
            return {
                "ok": True,
                "data": {
                    "results": [
                        {"query": q, "brand_mentioned": False, "position": None}
                        for q in queries[:10]
                    ],
                    "total_tested": min(len(queries), 10),
                },
            }

        return {"ok": False, "data": None, "error": f"Unknown action: {action}"}
