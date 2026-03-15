"""
src/tools/data/d2c_benchmarks.py  (AM-73)

Proprietary Indian D2C benchmarks database.
Stores and retrieves industry benchmarks for CAC, LTV, ROAS, AOV etc.
by category, channel, and stage.
"""

from __future__ import annotations

import logging
from typing import Any

from src.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

# Hardcoded Indian D2C benchmarks by category
_BENCHMARKS: dict[str, dict[str, Any]] = {
    "personal_care": {
        "cac_inr": {"median": 350, "p25": 200, "p75": 600},
        "ltv_inr": {"median": 1800, "p25": 900, "p75": 3500},
        "roas": {"median": 3.2, "p25": 2.0, "p75": 5.0},
        "aov_inr": {"median": 450, "p25": 250, "p75": 800},
        "repeat_rate_pct": {"median": 28, "p25": 15, "p75": 42},
        "meta_ctr_pct": {"median": 1.8, "p25": 1.0, "p75": 3.0},
    },
    "food_beverage": {
        "cac_inr": {"median": 250, "p25": 120, "p75": 450},
        "ltv_inr": {"median": 2200, "p25": 1200, "p75": 4000},
        "roas": {"median": 4.0, "p25": 2.5, "p75": 6.5},
        "aov_inr": {"median": 550, "p25": 300, "p75": 900},
        "repeat_rate_pct": {"median": 35, "p25": 20, "p75": 50},
        "meta_ctr_pct": {"median": 2.0, "p25": 1.2, "p75": 3.5},
    },
    "fashion": {
        "cac_inr": {"median": 500, "p25": 300, "p75": 900},
        "ltv_inr": {"median": 2500, "p25": 1500, "p75": 5000},
        "roas": {"median": 2.5, "p25": 1.5, "p75": 4.0},
        "aov_inr": {"median": 1200, "p25": 600, "p75": 2500},
        "repeat_rate_pct": {"median": 22, "p25": 12, "p75": 35},
        "meta_ctr_pct": {"median": 1.5, "p25": 0.8, "p75": 2.5},
    },
}


class D2CBenchmarksTool(BaseTool):
    slug = "d2c_benchmarks"

    async def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        self._log_call(action, params)

        if action == "get_benchmarks":
            category = params.get("category", "personal_care")
            benchmarks = _BENCHMARKS.get(category)
            if benchmarks is None:
                return {"ok": True, "data": {"categories": list(_BENCHMARKS.keys()), "error": "Unknown category"}}
            return {"ok": True, "data": {"category": category, "benchmarks": benchmarks}}

        elif action == "compare_metric":
            category = params.get("category", "personal_care")
            metric = params.get("metric", "cac_inr")
            value = params.get("value", 0)
            benchmarks = _BENCHMARKS.get(category, {})
            bench = benchmarks.get(metric, {})
            median = bench.get("median", 0)
            percentile = "above_median" if value > median else "below_median"
            return {"ok": True, "data": {"metric": metric, "value": value, "median": median, "position": percentile}}

        elif action == "list_categories":
            return {"ok": True, "data": {"categories": list(_BENCHMARKS.keys())}}

        return {"ok": False, "data": None, "error": f"Unknown action: {action}"}
