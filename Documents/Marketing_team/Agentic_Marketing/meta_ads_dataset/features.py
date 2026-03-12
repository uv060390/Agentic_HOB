"""
features.py – Feature engineering for Meta Ad creatives.

Transforms raw RawAd objects + vision/transcript analysis results into a
flat feature dictionary suitable for a Pandas DataFrame or ML model input.

Feature groups
--------------
1. Performance metrics  – spend / impression mid-points, derived CPM, etc.
2. Ad format            – one-hot encoded ad format category
3. Creative signals     – vision analysis booleans / categorical fields
4. Text features        – body length, CTA presence, sentiment
5. Demographic features – age/gender distribution entropy, top segment
6. Temporal features    – flight duration, recency
"""

import math
import statistics
from datetime import datetime, timezone
from typing import Optional

from .collector import RawAd


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_features(
    ad: RawAd,
    vision_analysis: Optional[dict] = None,
    transcript: Optional[str] = None,
) -> dict:
    """
    Return a flat feature dict for a single ad.

    Parameters
    ----------
    ad : RawAd
        Raw ad record from MetaAdsCollector.
    vision_analysis : dict, optional
        Output of CreativeAnalyzer.analyse_image().
    transcript : str, optional
        Output of CreativeAnalyzer.transcribe_video().
    """
    features: dict = {}
    features.update(_performance_features(ad))
    features.update(_format_features(ad))
    features.update(_creative_features(vision_analysis or {}))
    features.update(_text_features(ad, transcript or ""))
    features.update(_demographic_features(ad))
    features.update(_temporal_features(ad))
    features.update(_metadata(ad))
    return features


# ---------------------------------------------------------------------------
# Feature groups
# ---------------------------------------------------------------------------

def _performance_features(ad: RawAd) -> dict:
    """Spend and impression estimates; derived CPM."""
    spend_mid = _range_midpoint(ad.spend)
    imp_mid = _range_midpoint(ad.impressions)

    cpm = (spend_mid / imp_mid * 1000) if imp_mid > 0 else None

    return {
        "spend_lower": _safe_float(ad.spend.get("lower_bound")),
        "spend_upper": _safe_float(ad.spend.get("upper_bound")),
        "spend_midpoint": spend_mid,
        "impressions_lower": _safe_float(ad.impressions.get("lower_bound")),
        "impressions_upper": _safe_float(ad.impressions.get("upper_bound")),
        "impressions_midpoint": imp_mid,
        "estimated_cpm": cpm,
    }


def _format_features(ad: RawAd) -> dict:
    """One-hot encode the four ad formats."""
    formats = ["IMAGE", "VIDEO", "CAROUSEL", "MEME"]
    return {f"format_{fmt.lower()}": int(ad.ad_format == fmt) for fmt in formats}


def _creative_features(va: dict) -> dict:
    """Boolean and categorical signals from Claude Vision analysis."""
    if not va or "error" in va:
        return {
            "vision_hook": None,
            "vision_cta": None,
            "vision_emotion": None,
            "vision_text_overlay": None,
            "vision_product_visible": None,
            "vision_people_visible": None,
            "vision_ugc_style": None,
            "vision_theme_count": None,
            "vision_brand_elements_count": None,
        }
    return {
        "vision_hook": va.get("hook"),
        "vision_cta": va.get("cta"),
        "vision_emotion": va.get("emotion"),
        "vision_text_overlay": int(bool(va.get("text_overlay"))),
        "vision_product_visible": int(bool(va.get("product_visible"))),
        "vision_people_visible": int(bool(va.get("people_visible"))),
        "vision_ugc_style": int(bool(va.get("ugc_style"))),
        "vision_theme_count": len(va.get("creative_themes") or []),
        "vision_brand_elements_count": len(va.get("brand_elements") or []),
    }


def _text_features(ad: RawAd, transcript: str) -> dict:
    """Simple text-derived features from ad bodies and transcript."""
    all_bodies = " ".join(ad.ad_creative_bodies)
    all_titles = " ".join(ad.ad_creative_link_titles)
    all_text = f"{all_bodies} {all_titles} {transcript}".strip()

    return {
        "body_char_length": len(all_bodies),
        "body_word_count": len(all_bodies.split()) if all_bodies else 0,
        "title_count": len(ad.ad_creative_link_titles),
        "has_transcript": int(len(transcript) > 0),
        "transcript_word_count": len(transcript.split()) if transcript else 0,
        "total_text_length": len(all_text),
        "keywords_matched_count": len(ad.keywords_matched),
        "publisher_platform_count": len(ad.publisher_platforms),
    }


def _demographic_features(ad: RawAd) -> dict:
    """
    Summarise demographic_distribution into aggregate features.

    demographic_distribution is a list of dicts like:
      {"age": "25-34", "gender": "female", "percentage": "0.42"}
    """
    dist = ad.demographic_distribution
    if not dist:
        return {
            "demo_age_entropy": None,
            "demo_gender_entropy": None,
            "demo_top_age_band": None,
            "demo_top_gender": None,
            "demo_female_pct": None,
            "demo_male_pct": None,
            "demo_region_count": len(ad.region_distribution),
        }

    age_weights: dict[str, float] = {}
    gender_weights: dict[str, float] = {}

    for entry in dist:
        age = entry.get("age", "unknown")
        gender = entry.get("gender", "unknown")
        pct = _safe_float(entry.get("percentage", 0))
        age_weights[age] = age_weights.get(age, 0.0) + pct
        gender_weights[gender] = gender_weights.get(gender, 0.0) + pct

    top_age = max(age_weights, key=age_weights.get) if age_weights else None
    top_gender = max(gender_weights, key=gender_weights.get) if gender_weights else None

    return {
        "demo_age_entropy": _entropy(list(age_weights.values())),
        "demo_gender_entropy": _entropy(list(gender_weights.values())),
        "demo_top_age_band": top_age,
        "demo_top_gender": top_gender,
        "demo_female_pct": gender_weights.get("female"),
        "demo_male_pct": gender_weights.get("male"),
        "demo_region_count": len(ad.region_distribution),
    }


def _temporal_features(ad: RawAd) -> dict:
    """Flight duration and recency features."""
    now = datetime.now(tz=timezone.utc)
    start = _parse_date(ad.ad_delivery_start_time)
    stop = _parse_date(ad.ad_delivery_stop_time) if ad.ad_delivery_stop_time else now

    flight_days = (stop - start).days if start else None
    days_since_start = (now - start).days if start else None
    is_active = int(ad.ad_delivery_stop_time is None)

    return {
        "flight_days": flight_days,
        "days_since_start": days_since_start,
        "is_active": is_active,
    }


def _metadata(ad: RawAd) -> dict:
    return {
        "ad_id": ad.ad_id,
        "page_id": ad.page_id,
        "page_name": ad.page_name,
        "ad_format": ad.ad_format,
        "currency": ad.currency,
        "languages": "|".join(ad.languages),
        "publisher_platforms": "|".join(ad.publisher_platforms),
        "keywords_matched": "|".join(ad.keywords_matched),
        "ad_snapshot_url": ad.ad_snapshot_url,
    }


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _range_midpoint(bounds: dict) -> float:
    lo = _safe_float(bounds.get("lower_bound", 0))
    hi = _safe_float(bounds.get("upper_bound", 0))
    return (lo + hi) / 2.0


def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _entropy(weights: list[float]) -> Optional[float]:
    total = sum(weights)
    if total == 0:
        return None
    probs = [w / total for w in weights if w > 0]
    return -sum(p * math.log2(p) for p in probs)


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None
