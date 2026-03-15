"""
scripts/seed_tool_registry.py  (AM-74)

Seed tool_registry entries for AIM (active tools) and LembasMax (wind-down subset).
Idempotent — safe to run multiple times.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.tools.tool_registry import register_tool


# AIM — full active brand, all tools enabled
AIM_TOOLS = [
    ("meta_ads", 500.0),
    ("google_ads", 500.0),
    ("amazon_ads", 200.0),
    ("shopify", 0.0),
    ("amazon_seller", 0.0),
    ("blinkit", 0.0),
    ("lovable_shopify", 50.0),
    ("chatgpt_aeo", 50.0),
    ("perplexity_aeo", 50.0),
    ("gmail", 0.0),
    ("whatsapp", 0.0),
    ("shiprocket", 0.0),
    ("delhivery", 0.0),
    ("fssai", 0.0),
    ("supabase_client", 0.0),
    ("d2c_benchmarks", 0.0),
    ("google_drive", 0.0),
    ("apify_fb_ads", 20.0),
]

# LembasMax — wind-down mode, only essential tools
LEMBASMAX_TOOLS = [
    ("shopify", 0.0),
    ("amazon_seller", 0.0),
    ("shiprocket", 0.0),
    ("gmail", 0.0),
    ("fssai", 0.0),
    ("supabase_client", 0.0),
]


async def main() -> None:
    print("Seeding tool_registry entries...")

    for slug, budget in AIM_TOOLS:
        entry_id = await register_tool("aim", slug, budget)
        print(f"  AIM: {slug} (budget=${budget:.2f}) → {entry_id}")

    for slug, budget in LEMBASMAX_TOOLS:
        entry_id = await register_tool("lembasmax", slug, budget)
        print(f"  LembasMax: {slug} (budget=${budget:.2f}) → {entry_id}")

    print(f"\nDone. {len(AIM_TOOLS)} AIM tools, {len(LEMBASMAX_TOOLS)} LembasMax tools.")


if __name__ == "__main__":
    asyncio.run(main())
