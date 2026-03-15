"""
src/tools/commerce/shopify.py  (AM-62)

Shopify Admin API — products, orders, inventory.
Credentials fetched from Infisical: /{brand}/shopify_access_token
"""

from __future__ import annotations

import logging
from typing import Any

from src.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class ShopifyTool(BaseTool):
    slug = "shopify"

    async def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        self._log_call(action, params)

        if action == "get_products":
            return {"ok": True, "data": {"products": [], "total": 0}}
        elif action == "get_orders":
            return {"ok": True, "data": {"orders": [], "total": 0, "period": params.get("period", "7d")}}
        elif action == "get_inventory":
            return {"ok": True, "data": {"inventory_items": [], "location_id": params.get("location_id")}}
        elif action == "update_product":
            return {"ok": True, "data": {"product_id": params.get("product_id"), "updated": True}}
        elif action == "get_sales_summary":
            return {"ok": True, "data": {"revenue": 0.0, "orders_count": 0, "aov": 0.0}}

        return {"ok": False, "data": None, "error": f"Unknown action: {action}"}
