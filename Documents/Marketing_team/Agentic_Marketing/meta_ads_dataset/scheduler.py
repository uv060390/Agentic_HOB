"""
scheduler.py – 48-hour cron re-check for ad Active/Inactive status.

Implements the target-variable update loop described in AM-2:
  "Implement a cron job/scheduled run that re-checks previously scraped Ad IDs
   every 48 hours to update their Active/Inactive status and calculate the
   total days the ad remained live."

Usage (standalone cron)
-----------------------
    python -m meta_ads_dataset.scheduler \
        --table meta_ads_creatives \
        --batch-size 100

This module is also importable for use inside an orchestrator or Airflow DAG.

Required env vars:
  APIFY_API_TOKEN   – Apify API token
  SUPABASE_URL      – Supabase project URL
  SUPABASE_KEY      – Supabase service/anon key
"""

import argparse
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

ACTOR_ID = "curious_coder/facebook-ads-library-scraper"


class AdStatusRefresher:
    """
    Re-checks the active/inactive status of previously scraped ads and
    updates ``days_active`` + ``is_active`` + ``last_checked_at`` in Supabase.

    Parameters
    ----------
    apify_api_token : str, optional
        Falls back to APIFY_API_TOKEN env var.
    supabase_url : str, optional
        Falls back to SUPABASE_URL / supabase_url env var.
    supabase_key : str, optional
        Falls back to SUPABASE_KEY / supabase_key env var.
    table : str
        Supabase table that holds the ad dataset.
    batch_size : int
        Number of ad IDs to re-check per Apify actor run.
    """

    def __init__(
        self,
        apify_api_token: Optional[str] = None,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        table: str = "meta_ads_creatives",
        batch_size: int = 100,
    ):
        from apify_client import ApifyClient
        from supabase import create_client

        token = apify_api_token or os.environ["APIFY_API_TOKEN"]
        self._apify = ApifyClient(token)

        url = supabase_url or os.environ.get("SUPABASE_URL") or os.environ.get("supabase_url")
        key = supabase_key or os.environ.get("SUPABASE_KEY") or os.environ.get("supabase_key")
        if not url or not key:
            raise EnvironmentError("SUPABASE_URL and SUPABASE_KEY must be set.")
        self._supabase = create_client(url, key)

        self.table = table
        self.batch_size = batch_size

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> int:
        """
        Fetch all tracked ad IDs from Supabase, re-check each against the
        Apify actor, and write updated status back.

        Returns the number of ads updated.
        """
        ad_ids = self._fetch_tracked_ad_ids()
        if not ad_ids:
            logger.info("No ads to re-check.")
            return 0

        logger.info("Re-checking %d ad IDs in batches of %d …", len(ad_ids), self.batch_size)
        updated = 0
        for i in range(0, len(ad_ids), self.batch_size):
            batch = ad_ids[i : i + self.batch_size]
            updates = self._check_batch(batch)
            self._write_updates(updates)
            updated += len(updates)
            logger.info("Batch %d/%d – updated %d ads", i // self.batch_size + 1, -(-len(ad_ids) // self.batch_size), len(updates))

        logger.info("Re-check complete. Total updated: %d", updated)
        return updated

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_tracked_ad_ids(self) -> list[str]:
        """Pull all ad_ids (plus start dates) currently stored in Supabase."""
        response = (
            self._supabase
            .table(self.table)
            .select("ad_id, ad_delivery_start_time")
            .execute()
        )
        return [row["ad_id"] for row in (response.data or [])]

    def _check_batch(self, ad_ids: list[str]) -> list[dict]:
        """
        Run the Apify actor for the given ad IDs and return a list of
        update dicts: {ad_id, is_active, days_active, last_checked_at}.
        """
        run_input = {
            "adArchiveIDs": ad_ids,
            "scrapeAdDetails": False,   # status check only — no media download
        }

        now = datetime.now(tz=timezone.utc)
        updates = []

        try:
            run = self._apify.actor(ACTOR_ID).call(run_input=run_input)
            dataset_id = run.get("defaultDatasetId")
            if not dataset_id:
                return updates

            for item in self._apify.dataset(dataset_id).iterate_items():
                ad_id = str(item.get("adArchiveID") or item.get("id", ""))
                if not ad_id:
                    continue

                start_str = item.get("startDate") or item.get("ad_delivery_start_time", "")
                end_str = item.get("endDate") or item.get("ad_delivery_stop_time")
                is_active = int(not end_str)

                days_active: Optional[int] = None
                if start_str:
                    from .features import _parse_date  # local import to avoid circular
                    start_dt = _parse_date(start_str)
                    if start_dt:
                        stop_dt = _parse_date(end_str) if end_str else now
                        days_active = (stop_dt - start_dt).days

                updates.append({
                    "ad_id": ad_id,
                    "is_active": is_active,
                    "days_active": days_active,
                    "flight_days": days_active,
                    "last_checked_at": now.isoformat(),
                })
        except Exception as exc:
            logger.error("Apify actor call failed for batch: %s", exc)

        return updates

    def _write_updates(self, updates: list[dict]) -> None:
        """Upsert status updates back into Supabase."""
        if not updates:
            return
        self._supabase.table(self.table).upsert(updates).execute()


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def _main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Re-check ad Active/Inactive status (run every 48 h).")
    parser.add_argument("--table", default="meta_ads_creatives", help="Supabase table name")
    parser.add_argument("--batch-size", type=int, default=100, help="Ads per Apify run")
    args = parser.parse_args()

    refresher = AdStatusRefresher(table=args.table, batch_size=args.batch_size)
    refresher.run()


if __name__ == "__main__":
    _main()
