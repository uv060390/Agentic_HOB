"""
collector.py – Fetch Meta Ad Library creatives for a list of keywords.

Uses the Meta Ad Library API:
  https://www.facebook.com/ads/library/api/

Required env vars:
  META_ACCESS_TOKEN  – a valid Facebook user/app access token with
                       ads_read permission.
"""

import os
import time
import logging
from typing import Optional
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

META_AD_LIBRARY_URL = "https://graph.facebook.com/v19.0/ads_archive"

AD_FORMATS = ["IMAGE", "VIDEO", "MEME", "CAROUSEL"]


@dataclass
class RawAd:
    ad_id: str
    page_id: str
    page_name: str
    ad_creative_bodies: list[str]
    ad_creative_link_captions: list[str]
    ad_creative_link_titles: list[str]
    ad_snapshot_url: str
    ad_delivery_start_time: str
    ad_delivery_stop_time: Optional[str]
    currency: str
    spend: dict                   # {"lower_bound": ..., "upper_bound": ...}
    impressions: dict             # {"lower_bound": ..., "upper_bound": ...}
    demographic_distribution: list[dict]
    region_distribution: list[dict]
    languages: list[str]
    publisher_platforms: list[str]
    ad_format: str               # IMAGE | VIDEO | MEME | CAROUSEL
    keywords_matched: list[str] = field(default_factory=list)
    media_urls: list[str] = field(default_factory=list)


class MetaAdsCollector:
    """
    Fetches ads from the Meta Ad Library API for given keywords.

    Parameters
    ----------
    access_token : str, optional
        Falls back to META_ACCESS_TOKEN env var.
    ad_reached_countries : list[str]
        ISO-3166 country codes to scope the search (default: ["US"]).
    ad_active_status : str
        "ALL" | "ACTIVE" | "INACTIVE" (default: "ALL").
    limit : int
        Max ads per keyword page request (capped at 1 000 by Meta).
    max_pages : int
        Max pagination pages to follow per keyword (0 = unlimited).
    request_delay : float
        Seconds to sleep between API calls to stay within rate limits.
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        ad_reached_countries: Optional[list[str]] = None,
        ad_active_status: str = "ALL",
        limit: int = 500,
        max_pages: int = 5,
        request_delay: float = 1.0,
    ):
        self.access_token = access_token or os.environ["META_ACCESS_TOKEN"]
        self.ad_reached_countries = ad_reached_countries or ["US"]
        self.ad_active_status = ad_active_status
        self.limit = min(limit, 1000)
        self.max_pages = max_pages
        self.request_delay = request_delay

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_by_keywords(self, keywords: list[str]) -> list[RawAd]:
        """Return a deduplicated list of RawAd objects across all keywords."""
        seen: dict[str, RawAd] = {}
        for kw in keywords:
            logger.info("Fetching Meta ads for keyword: %s", kw)
            for ad in self._paginate(kw):
                if ad.ad_id not in seen:
                    seen[ad.ad_id] = ad
                else:
                    seen[ad.ad_id].keywords_matched.append(kw)
        return list(seen.values())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _paginate(self, keyword: str):
        params = self._base_params(keyword)
        pages_fetched = 0
        url = META_AD_LIBRARY_URL

        while url:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            for raw in data.get("data", []):
                yield self._parse(raw, keyword)

            pages_fetched += 1
            next_cursor = data.get("paging", {}).get("next")
            if not next_cursor or (self.max_pages and pages_fetched >= self.max_pages):
                break

            # Subsequent requests use the full next URL from the cursor
            url = next_cursor
            params = {}  # params are embedded in the cursor URL
            time.sleep(self.request_delay)

    def _base_params(self, keyword: str) -> dict:
        return {
            "access_token": self.access_token,
            "ad_type": "POLITICAL_AND_ISSUE_ADS",  # use "ALL" for non-political
            "ad_reached_countries": self.ad_reached_countries,
            "search_terms": keyword,
            "ad_active_status": self.ad_active_status,
            "fields": ",".join([
                "id",
                "page_id",
                "page_name",
                "ad_creative_bodies",
                "ad_creative_link_captions",
                "ad_creative_link_titles",
                "ad_snapshot_url",
                "ad_delivery_start_time",
                "ad_delivery_stop_time",
                "currency",
                "spend",
                "impressions",
                "demographic_distribution",
                "region_distribution",
                "languages",
                "publisher_platforms",
            ]),
            "limit": self.limit,
        }

    @staticmethod
    def _parse(raw: dict, keyword: str) -> RawAd:
        return RawAd(
            ad_id=raw.get("id", ""),
            page_id=raw.get("page_id", ""),
            page_name=raw.get("page_name", ""),
            ad_creative_bodies=raw.get("ad_creative_bodies") or [],
            ad_creative_link_captions=raw.get("ad_creative_link_captions") or [],
            ad_creative_link_titles=raw.get("ad_creative_link_titles") or [],
            ad_snapshot_url=raw.get("ad_snapshot_url", ""),
            ad_delivery_start_time=raw.get("ad_delivery_start_time", ""),
            ad_delivery_stop_time=raw.get("ad_delivery_stop_time"),
            currency=raw.get("currency", ""),
            spend=raw.get("spend") or {},
            impressions=raw.get("impressions") or {},
            demographic_distribution=raw.get("demographic_distribution") or [],
            region_distribution=raw.get("region_distribution") or [],
            languages=raw.get("languages") or [],
            publisher_platforms=raw.get("publisher_platforms") or [],
            ad_format=_infer_format(raw),
            keywords_matched=[keyword],
            media_urls=_extract_media_urls(raw),
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _infer_format(raw: dict) -> str:
    """Best-effort format inference from the ad_snapshot_url / bodies."""
    snapshot = raw.get("ad_snapshot_url", "").lower()
    if "carousel" in snapshot:
        return "CAROUSEL"
    # Heuristic: multiple bodies typically means carousel
    bodies = raw.get("ad_creative_bodies") or []
    if len(bodies) > 1:
        return "CAROUSEL"
    # The Ad Library API doesn't expose format directly for non-political ads;
    # in a production integration you'd call the creative detail endpoint.
    return "IMAGE"


def _extract_media_urls(raw: dict) -> list[str]:
    """Placeholder – real implementation would call the snapshot API."""
    snapshot = raw.get("ad_snapshot_url")
    return [snapshot] if snapshot else []
