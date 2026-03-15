"""
src/tools/logistics/shiprocket.py  (AM-69)

Shiprocket API — order fulfilment, tracking.
Credentials fetched from Infisical: /{brand}/shiprocket_token
"""

from __future__ import annotations

import logging
from typing import Any

from src.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class ShiprocketTool(BaseTool):
    slug = "shiprocket"

    async def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        self._log_call(action, params)

        if action == "create_shipment":
            return {"ok": True, "data": {"shipment_id": "mock-ship-id", "order_id": params.get("order_id")}}
        elif action == "track_shipment":
            return {"ok": True, "data": {"shipment_id": params.get("shipment_id"), "status": "in_transit", "eta": "2d"}}
        elif action == "get_rates":
            return {"ok": True, "data": {"rates": [], "pickup_pincode": params.get("pickup"), "delivery_pincode": params.get("delivery")}}
        elif action == "get_orders":
            return {"ok": True, "data": {"orders": [], "total": 0}}

        return {"ok": False, "data": None, "error": f"Unknown action: {action}"}
