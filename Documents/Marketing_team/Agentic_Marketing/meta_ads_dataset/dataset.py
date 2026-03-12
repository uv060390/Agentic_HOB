"""
dataset.py – Orchestrates the full Meta Ads competitor creative dataset pipeline.

Usage
-----
    from meta_ads_dataset import MetaAdsDataset

    ds = MetaAdsDataset()
    df = ds.build(
        keywords=["skincare routine", "SPF sunscreen", "anti-aging serum"],
        ad_reached_countries=["US", "GB"],
    )
    df.to_csv("meta_ads_competitor_creatives.csv", index=False)
    ds.push_to_supabase(df, table="meta_ads_creatives")
"""

import logging
import os
from typing import Optional

import pandas as pd
from tqdm import tqdm

from .analyzer import CreativeAnalyzer
from .collector import ApifyMetaAdsCollector, RawAd
from .features import build_features

logger = logging.getLogger(__name__)


class MetaAdsDataset:
    """
    End-to-end pipeline that:
      1. Fetches competitor ads via the Apify Meta Ads Scraper actor
      2. Analyses each creative with Claude Vision + Whisper
      3. Engineers a feature set per ad (including ``days_active`` ML target)
      4. Returns a single enriched Pandas DataFrame
      5. Can push the dataset to Supabase

    Parameters
    ----------
    collector : ApifyMetaAdsCollector, optional
        Custom collector; built with defaults if omitted.
    analyzer : CreativeAnalyzer, optional
        Custom analyzer; built with defaults if omitted.
    analyse_creatives : bool
        Set to False to skip vision/transcript analysis (faster for testing).
    max_ads : int, optional
        Cap total ads processed (useful for cost-controlled experiments).
    """

    def __init__(
        self,
        collector: Optional[ApifyMetaAdsCollector] = None,
        analyzer: Optional[CreativeAnalyzer] = None,
        analyse_creatives: bool = True,
        max_ads: Optional[int] = None,
    ):
        self.collector = collector or ApifyMetaAdsCollector()
        self.analyzer = analyzer or (CreativeAnalyzer() if analyse_creatives else None)
        self.analyse_creatives = analyse_creatives and self.analyzer is not None
        self.max_ads = max_ads

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        keywords: list[str],
        ad_reached_countries: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """
        Collect, analyse, and featurise Meta ads for the given keywords.

        Parameters
        ----------
        keywords : list[str]
            Industry-trend keywords (e.g. ["SPF 50", "vegan protein"]).
        ad_reached_countries : list[str], optional
            Override the collector's country scope for this run.

        Returns
        -------
        pd.DataFrame
            One row per ad.  ``days_active`` is the ML target variable.
        """
        if ad_reached_countries:
            self.collector.ad_reached_countries = ad_reached_countries

        logger.info("Step 1/3 – Collecting ads for %d keywords via Apify …", len(keywords))
        raw_ads: list[RawAd] = self.collector.fetch_by_keywords(keywords)

        if self.max_ads:
            raw_ads = raw_ads[: self.max_ads]

        logger.info("Collected %d unique ads.", len(raw_ads))

        rows = []
        for ad in tqdm(raw_ads, desc="Building features", unit="ad"):
            vision_analysis: dict = {}
            transcript: str = ""

            if self.analyse_creatives and ad.media_urls:
                logger.debug("Step 2/3 – Analysing creative for ad %s", ad.ad_id)
                creative_result = self.analyzer.analyse_creative(
                    media_url=ad.media_urls[0],
                    ad_format=ad.ad_format,
                )
                vision_analysis = creative_result.get("vision_analysis", {})
                transcript = creative_result.get("transcript", "")

            logger.debug("Step 3/3 – Engineering features for ad %s", ad.ad_id)
            row = build_features(ad, vision_analysis=vision_analysis, transcript=transcript)
            rows.append(row)

        df = pd.DataFrame(rows)
        df = self._post_process(df)
        logger.info("Dataset ready: %d rows × %d columns", *df.shape)
        return df

    def push_to_supabase(self, df: pd.DataFrame, table: str = "meta_ads_creatives") -> None:
        """
        Upload the dataset to a Supabase table.

        Requires env vars: SUPABASE_URL and SUPABASE_KEY.
        The DataFrame index (ad_id) is reset to a column before upload.

        Parameters
        ----------
        df : pd.DataFrame
            Enriched dataset returned by ``build()``.
        table : str
            Target Supabase table name.
        """
        try:
            from supabase import create_client
        except ImportError as exc:
            raise ImportError("Install supabase-py: pip install supabase") from exc

        url = os.environ.get("SUPABASE_URL") or os.environ.get("supabase_url")
        key = os.environ.get("SUPABASE_KEY") or os.environ.get("supabase_key")
        if not url or not key:
            raise EnvironmentError("SUPABASE_URL and SUPABASE_KEY must be set.")

        client = create_client(url, key)

        records = df.reset_index().to_dict(orient="records")
        # Supabase upsert in batches of 500
        batch_size = 500
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            client.table(table).upsert(batch).execute()
            logger.info("Pushed rows %d–%d to Supabase table '%s'", i, i + len(batch), table)

        logger.info("Supabase upload complete: %d rows → '%s'", len(records), table)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _post_process(df: pd.DataFrame) -> pd.DataFrame:
        """Sort columns – ``days_active`` first as the ML target."""
        if df.empty:
            return df

        target_cols = ["days_active"]
        meta_cols = ["ad_id", "page_id", "page_name", "ad_format", "keywords_matched"]
        perf_cols = [c for c in df.columns if c.startswith(("spend_", "impressions_", "estimated_"))]
        format_cols = [c for c in df.columns if c.startswith("format_")]
        vision_cols = [c for c in df.columns if c.startswith("vision_")]
        text_cols = [c for c in df.columns if c in (
            "body_char_length", "body_word_count", "title_count",
            "has_transcript", "transcript_word_count", "total_text_length",
            "keywords_matched_count", "publisher_platform_count",
        )]
        demo_cols = [c for c in df.columns if c.startswith("demo_")]
        temporal_cols = [c for c in df.columns if c in (
            "flight_days", "days_since_start", "is_active", "last_checked_at"
        )]
        other_cols = [c for c in df.columns if c not in (
            target_cols + meta_cols + perf_cols + format_cols + vision_cols
            + text_cols + demo_cols + temporal_cols
        )]

        ordered = target_cols + meta_cols + perf_cols + format_cols + vision_cols + text_cols + demo_cols + temporal_cols + other_cols
        ordered = [c for c in ordered if c in df.columns]
        return df[ordered].set_index("ad_id")
