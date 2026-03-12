"""
Meta Ads Competitor Creative Dataset Pipeline (AM-2)

Collects Meta Ad Library creatives by keyword, analyses them with
Claude Vision (images) and OpenAI Whisper (video/UGC audio), engineers
performance-metric features, categorises by ad format, and attaches
demographic targeting data — producing a single enriched DataFrame ready
for downstream modelling and strategy analysis.
"""

from .collector import MetaAdsCollector
from .analyzer import CreativeAnalyzer
from .features import build_features
from .dataset import MetaAdsDataset

__all__ = ["MetaAdsCollector", "CreativeAnalyzer", "build_features", "MetaAdsDataset"]
