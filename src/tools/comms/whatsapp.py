"""
src/tools/comms/whatsapp.py  (AM-68)

WhatsApp Business API outbound messaging tool.
Used by agents to send outbound messages (supplier updates, customer comms).
Credentials fetched from Infisical: /{brand}/whatsapp_api_token
"""

from __future__ import annotations

import logging
from typing import Any

from src.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class WhatsAppTool(BaseTool):
    slug = "whatsapp"

    async def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        self._log_call(action, params)

        if action == "send_message":
            return {
                "ok": True,
                "data": {
                    "message_id": "mock-wa-msg-id",
                    "to": params.get("to"),
                    "status": "sent",
                },
            }
        elif action == "send_template":
            return {
                "ok": True,
                "data": {
                    "message_id": "mock-wa-template-id",
                    "template": params.get("template_name"),
                    "to": params.get("to"),
                    "status": "sent",
                },
            }

        return {"ok": False, "data": None, "error": f"Unknown action: {action}"}
