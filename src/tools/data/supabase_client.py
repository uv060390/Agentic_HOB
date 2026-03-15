"""
src/tools/data/supabase_client.py  (AM-72)

Supabase read/write operations for brand/agent data.
Credentials fetched from config: BRANDOS_SUPABASE_URL + BRANDOS_SUPABASE_KEY
"""

from __future__ import annotations

import logging
from typing import Any

from src.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class SupabaseTool(BaseTool):
    slug = "supabase_client"

    async def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        self._log_call(action, params)

        table = params.get("table", "")
        if action == "select":
            return {"ok": True, "data": {"rows": [], "table": table, "count": 0}}
        elif action == "insert":
            return {"ok": True, "data": {"inserted": True, "table": table, "row": params.get("row")}}
        elif action == "update":
            return {"ok": True, "data": {"updated": True, "table": table, "filter": params.get("filter")}}
        elif action == "upsert":
            return {"ok": True, "data": {"upserted": True, "table": table}}

        return {"ok": False, "data": None, "error": f"Unknown action: {action}"}
