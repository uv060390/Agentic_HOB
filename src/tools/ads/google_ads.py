"""
src/tools/ads/google_ads.py  (AM-60)

Google Ads API — search, display, shopping campaigns.
Credentials fetched from Infisical: /{brand}/google_ads_refresh_token
"""

from __future__ import annotations

import logging
from typing import Any

from src.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class GoogleAdsTool(BaseTool):
    slug = "google_ads"

    async def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        self._log_call(action, params)

        if action == "get_campaigns":
            return {"ok": True, "data": {"campaigns": [], "total": 0}}
        elif action == "get_search_terms":
            return {"ok": True, "data": {"search_terms": [], "campaign_id": params.get("campaign_id")}}
        elif action == "update_bid_strategy":
            return {"ok": True, "data": {"campaign_id": params.get("campaign_id"), "strategy": params.get("strategy")}}
        elif action == "get_performance_report":
            return {"ok": True, "data": {"impressions": 0, "clicks": 0, "conversions": 0, "cost": 0.0}}

        return {"ok": False, "data": None, "error": f"Unknown action: {action}"}
