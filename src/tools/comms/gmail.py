"""
src/tools/comms/gmail.py  (AM-67)

Gmail API — send, read, draft supplier emails.
Credentials fetched from Infisical: /{brand}/gmail_service_account
"""

from __future__ import annotations

import logging
from typing import Any

from src.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class GmailTool(BaseTool):
    slug = "gmail"

    async def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        self._log_call(action, params)

        if action == "send_email":
            return {"ok": True, "data": {"message_id": "mock-msg-id", "to": params.get("to"), "sent": True}}
        elif action == "read_inbox":
            return {"ok": True, "data": {"messages": [], "total": 0, "query": params.get("query", "")}}
        elif action == "create_draft":
            return {"ok": True, "data": {"draft_id": "mock-draft-id", "to": params.get("to")}}
        elif action == "search":
            return {"ok": True, "data": {"messages": [], "query": params.get("query", "")}}

        return {"ok": False, "data": None, "error": f"Unknown action: {action}"}
