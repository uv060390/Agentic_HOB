"""
Meta Ads Competitor Creative Dataset Pipeline (AM-2)

Collects Meta Ad Library creatives via the Apify scraper actor, analyses them
with Claude Vision (images) and OpenAI Whisper (video/UGC audio), engineers
performance-metric features (including the ``days_active`` ML target variable),
categorises by ad format, attaches demographic targeting data — and pushes the
unified dataset to Supabase.
"""

from .collector import ApifyMetaAdsCollector, RawAd
from .analyzer import CreativeAnalyzer
from .features import build_features
from .dataset import MetaAdsDataset
from .scheduler import AdStatusRefresher

__all__ = [
    "ApifyMetaAdsCollector",
    "RawAd",
    "CreativeAnalyzer",
    "build_features",
    "MetaAdsDataset",
    "AdStatusRefresher",
]
