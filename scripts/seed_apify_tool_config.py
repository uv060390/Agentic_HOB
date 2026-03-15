"""
scripts/seed_apify_tool_config.py

Seeds the Apify Facebook Ads Library scraper as a custom tool config
for AIM brand. Uses custom_adapter.py at runtime — no dedicated module needed.

Idempotent: safe to run multiple times.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys


async def main() -> None:
    db_url = os.environ.get("BRANDOS_DB_URL")
    if not db_url:
        print("ERROR: BRANDOS_DB_URL environment variable not set.", file=sys.stderr)
        sys.exit(1)

    apify_config = {
        "tool_slug": "apify_fb_ads",
        "base_url": "https://api.apify.com/v2",
        "auth_type": "api_key_header",
        "auth_header": "Authorization",
        "secret_ref": "aim/apify_token",  # Infisical path — scoped to AIM brand
        "endpoints": {
            "run_scraper": {
                "method": "POST",
                "path": "/acts/curious_coder~facebook-ads-library-scraper/runs",
                "body_schema": {
                    "searchQuery": "string",
                    "country": "string",
                    "adType": "string",
                },
            },
            "get_results": {
                "method": "GET",
                "path": "/datasets/{datasetId}/items",
                "params": ["offset", "limit", "format"],
            },
        },
    }

    print("Seeding Apify Facebook Ads Library tool config for AIM...")
    print(f"Config: {json.dumps(apify_config, indent=2)}")
    print("\n[STUB] In production: INSERT INTO tool_config (company_id, tool_slug, config_json, secret_ref)")
    print("       WHERE company = 'aim' ON CONFLICT DO NOTHING")
    print("\nDone. Run 'alembic upgrade head' then this script against a live DB.")


if __name__ == "__main__":
    asyncio.run(main())
