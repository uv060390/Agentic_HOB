"""
collector.py – Fetch Meta Ad Library creatives via the Apify platform.

Uses the Apify Meta Ads Scraper actor (curious_coder/facebook-ads-library-scraper)
via the apify-client Python SDK.  This replaces direct Meta Ad Library API calls
so that proxy rotation and DOM-obfuscation bypass are handled by Apify.

Required env vars:
  APIFY_API_TOKEN  – Apify API token (https://console.apify.com/account/integrations)
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass, field

from apify_client import ApifyClient

logger = logging.getLogger(__name__)

ACTOR_ID = "curious_coder/facebook-ads-library-scraper"


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
    # Raw downloadable media URLs (.mp4 or .jpg) — NOT HTML snapshot links
    media_urls: list[str] = field(default_factory=list)


class ApifyMetaAdsCollector:
    """
    Fetches ads from the Meta Ad Library via Apify's scraper actor.

    Apify handles proxy rotation and Meta's DOM obfuscation so we get
    raw, downloadable media URLs (.mp4 / .jpg) directly.

    Parameters
    ----------
    apify_api_token : str, optional
        Falls back to APIFY_API_TOKEN env var.
    ad_reached_countries : list[str]
        ISO-3166 country codes (default: ["US"]).
    ad_active_status : str
        "ALL" | "ACTIVE" | "INACTIVE" (default: "ALL").
    max_ads_per_keyword : int
        Cap on ads retrieved per keyword (default: 200).
    """

    def __init__(
        self,
        apify_api_token: Optional[str] = None,
        ad_reached_countries: Optional[list[str]] = None,
        ad_active_status: str = "ALL",
        max_ads_per_keyword: int = 200,
    ):
        token = apify_api_token or os.environ["APIFY_API_TOKEN"]
        self._client = ApifyClient(token)
        self.ad_reached_countries = ad_reached_countries or ["US"]
        self.ad_active_status = ad_active_status
        self.max_ads_per_keyword = max_ads_per_keyword

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_by_keywords(self, keywords: list[str]) -> list[RawAd]:
        """Return a deduplicated list of RawAd objects across all keywords."""
        seen: dict[str, RawAd] = {}
        for kw in keywords:
            logger.info("Running Apify actor for keyword: %s", kw)
            for ad in self._run_actor(kw):
                if ad.ad_id not in seen:
                    seen[ad.ad_id] = ad
                else:
                    seen[ad.ad_id].keywords_matched.append(kw)
        return list(seen.values())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_actor(self, keyword: str):
        """Trigger the Apify actor and yield parsed RawAd objects."""
        run_input = {
            "searchTerms": [keyword],
            "adReachedCountries": self.ad_reached_countries,
            "adActiveStatus": self.ad_active_status,
            "maxResults": self.max_ads_per_keyword,
            "scrapeAdDetails": True,   # navigate snapshot URL → raw media URLs
        }

        run = self._client.actor(ACTOR_ID).call(run_input=run_input)
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            logger.warning("No dataset returned for keyword: %s", keyword)
            return

        items = self._client.dataset(dataset_id).iterate_items()
        for item in items:
            try:
                yield self._parse(item, keyword)
            except Exception as exc:
                logger.warning("Failed to parse ad item: %s – %s", item.get("adArchiveID"), exc)

    @staticmethod
    def _parse(item: dict, keyword: str) -> RawAd:
        return RawAd(
            ad_id=str(item.get("adArchiveID") or item.get("id", "")),
            page_id=str(item.get("pageID") or item.get("page_id", "")),
            page_name=item.get("pageName") or item.get("page_name", ""),
            ad_creative_bodies=item.get("adCreativeBodies") or item.get("ad_creative_bodies") or [],
            ad_creative_link_captions=item.get("adCreativeLinkCaptions") or item.get("ad_creative_link_captions") or [],
            ad_creative_link_titles=item.get("adCreativeLinkTitles") or item.get("ad_creative_link_titles") or [],
            ad_snapshot_url=item.get("snapshotUrl") or item.get("ad_snapshot_url", ""),
            ad_delivery_start_time=item.get("startDate") or item.get("ad_delivery_start_time", ""),
            ad_delivery_stop_time=item.get("endDate") or item.get("ad_delivery_stop_time"),
            currency=item.get("currency", ""),
            spend=_parse_range(item.get("spend")),
            impressions=_parse_range(item.get("impressions")),
            demographic_distribution=item.get("demographicDistribution") or item.get("demographic_distribution") or [],
            region_distribution=item.get("regionDistribution") or item.get("region_distribution") or [],
            languages=item.get("languages") or [],
            publisher_platforms=item.get("publisherPlatforms") or item.get("publisher_platforms") or [],
            ad_format=_infer_format(item),
            keywords_matched=[keyword],
            media_urls=_extract_raw_media_urls(item),
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _parse_range(value) -> dict:
    """Normalise spend/impressions into {lower_bound, upper_bound} dict."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        # e.g. "1000-4999"
        parts = value.split("-")
        if len(parts) == 2:
            return {"lower_bound": parts[0], "upper_bound": parts[1]}
    return {}


def _infer_format(item: dict) -> str:
    """Infer ad format from Apify actor output."""
    # Actor may return explicit format field
    fmt = (item.get("adFormat") or item.get("ad_format") or "").upper()
    if fmt in ("IMAGE", "VIDEO", "CAROUSEL", "MEME"):
        return fmt

    videos = item.get("videos") or []
    images = item.get("images") or []
    if videos:
        return "VIDEO"
    if len(images) > 1:
        return "CAROUSEL"
    if images:
        return "IMAGE"
    return "IMAGE"


def _extract_raw_media_urls(item: dict) -> list[str]:
    """
    Extract raw downloadable media URLs (.mp4 / .jpg) from the Apify output.

    Apify's scraper navigates the ad_snapshot_url and returns actual media
    assets rather than the HTML snapshot link — which AI APIs cannot process.
    """
    urls: list[str] = []

    # Video URLs (prefer HD, fall back to SD)
    for video in item.get("videos") or []:
        url = video.get("videoHdUrl") or video.get("videoSdUrl") or video.get("videoPrvUrl")
        if url:
            urls.append(url)

    # Image URLs
    for image in item.get("images") or []:
        url = image.get("resizedImageUrl") or image.get("originalImageUrl")
        if url:
            urls.append(url)

    # Carousel cards
    for card in item.get("cards") or []:
        for image in card.get("images") or []:
            url = image.get("resizedImageUrl") or image.get("originalImageUrl")
            if url:
                urls.append(url)
        for video in card.get("videos") or []:
            url = video.get("videoHdUrl") or video.get("videoSdUrl")
            if url:
                urls.append(url)

    return urls
