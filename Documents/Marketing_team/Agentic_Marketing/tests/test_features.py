"""Unit tests for the feature engineering layer (no API calls needed)."""

import math
import pytest

from meta_ads_dataset.collector import RawAd
from meta_ads_dataset.features import build_features, _entropy, _range_midpoint


def _make_ad(**overrides) -> RawAd:
    defaults = dict(
        ad_id="123",
        page_id="p1",
        page_name="Brand X",
        ad_creative_bodies=["Buy now and save 20%!"],
        ad_creative_link_captions=["brandx.com"],
        ad_creative_link_titles=["Summer Sale"],
        ad_snapshot_url="https://example.com/snapshot/123",
        ad_delivery_start_time="2024-01-01",
        ad_delivery_stop_time="2024-03-01",
        currency="USD",
        spend={"lower_bound": "100", "upper_bound": "500"},
        impressions={"lower_bound": "10000", "upper_bound": "50000"},
        demographic_distribution=[
            {"age": "18-24", "gender": "female", "percentage": "0.3"},
            {"age": "25-34", "gender": "female", "percentage": "0.4"},
            {"age": "25-34", "gender": "male", "percentage": "0.3"},
        ],
        region_distribution=[{"region": "California", "percentage": "0.6"}],
        languages=["en"],
        publisher_platforms=["facebook", "instagram"],
        ad_format="IMAGE",
        keywords_matched=["skincare"],
        media_urls=["https://example.com/image.jpg"],
    )
    defaults.update(overrides)
    return RawAd(**defaults)


class TestPerformanceFeatures:
    def test_spend_midpoint(self):
        ad = _make_ad(spend={"lower_bound": "100", "upper_bound": "500"})
        f = build_features(ad)
        assert f["spend_midpoint"] == pytest.approx(300.0)

    def test_impressions_midpoint(self):
        ad = _make_ad(impressions={"lower_bound": "10000", "upper_bound": "50000"})
        f = build_features(ad)
        assert f["impressions_midpoint"] == pytest.approx(30000.0)

    def test_estimated_cpm(self):
        # spend_mid=300, imp_mid=30000 → CPM = 300/30000 * 1000 = 10
        ad = _make_ad(
            spend={"lower_bound": "100", "upper_bound": "500"},
            impressions={"lower_bound": "10000", "upper_bound": "50000"},
        )
        f = build_features(ad)
        assert f["estimated_cpm"] == pytest.approx(10.0)

    def test_zero_impressions_cpm_is_none(self):
        ad = _make_ad(impressions={"lower_bound": "0", "upper_bound": "0"})
        f = build_features(ad)
        assert f["estimated_cpm"] is None


class TestFormatFeatures:
    @pytest.mark.parametrize("fmt", ["IMAGE", "VIDEO", "CAROUSEL", "MEME"])
    def test_one_hot_encoding(self, fmt):
        ad = _make_ad(ad_format=fmt)
        f = build_features(ad)
        assert f[f"format_{fmt.lower()}"] == 1
        for other in ["IMAGE", "VIDEO", "CAROUSEL", "MEME"]:
            if other != fmt:
                assert f[f"format_{other.lower()}"] == 0


class TestCreativeFeatures:
    def test_vision_flags_parsed(self):
        vision = {
            "hook": "Transform your skin",
            "cta": "Shop Now",
            "emotion": "aspiration",
            "text_overlay": True,
            "product_visible": True,
            "people_visible": False,
            "ugc_style": False,
            "creative_themes": ["lifestyle", "before_after"],
            "brand_elements": ["logo"],
        }
        ad = _make_ad()
        f = build_features(ad, vision_analysis=vision)
        assert f["vision_text_overlay"] == 1
        assert f["vision_product_visible"] == 1
        assert f["vision_people_visible"] == 0
        assert f["vision_theme_count"] == 2
        assert f["vision_brand_elements_count"] == 1

    def test_missing_vision_returns_none_fields(self):
        ad = _make_ad()
        f = build_features(ad, vision_analysis=None)
        assert f["vision_emotion"] is None


class TestTextFeatures:
    def test_body_char_length(self):
        ad = _make_ad(ad_creative_bodies=["Hello world"])
        f = build_features(ad)
        assert f["body_char_length"] == len("Hello world")

    def test_transcript_word_count(self):
        ad = _make_ad()
        f = build_features(ad, transcript="This is a great product")
        assert f["transcript_word_count"] == 5
        assert f["has_transcript"] == 1

    def test_no_transcript(self):
        ad = _make_ad()
        f = build_features(ad)
        assert f["has_transcript"] == 0
        assert f["transcript_word_count"] == 0


class TestDemographicFeatures:
    def test_top_age_band(self):
        ad = _make_ad()
        f = build_features(ad)
        # 25-34 females (0.4) + 25-34 males (0.3) = 0.7 → dominant age band
        assert f["demo_top_age_band"] == "25-34"

    def test_entropy_is_non_negative(self):
        ad = _make_ad()
        f = build_features(ad)
        assert f["demo_age_entropy"] >= 0

    def test_empty_demographics(self):
        ad = _make_ad(demographic_distribution=[])
        f = build_features(ad)
        assert f["demo_top_age_band"] is None
        assert f["demo_age_entropy"] is None


class TestTemporalFeatures:
    def test_flight_days(self):
        ad = _make_ad(
            ad_delivery_start_time="2024-01-01",
            ad_delivery_stop_time="2024-03-01",
        )
        f = build_features(ad)
        assert f["flight_days"] == 60  # Jan(31) + Feb(29 in 2024)

    def test_active_ad(self):
        ad = _make_ad(ad_delivery_stop_time=None)
        f = build_features(ad)
        assert f["is_active"] == 1


class TestEntropyHelper:
    def test_uniform_distribution(self):
        # 4 equal buckets → entropy = 2.0 bits
        assert _entropy([0.25, 0.25, 0.25, 0.25]) == pytest.approx(2.0)

    def test_single_bucket(self):
        assert _entropy([1.0]) == pytest.approx(0.0)

    def test_empty(self):
        assert _entropy([]) is None


class TestRangeMidpoint:
    def test_basic(self):
        assert _range_midpoint({"lower_bound": "100", "upper_bound": "300"}) == pytest.approx(200.0)

    def test_missing_keys(self):
        assert _range_midpoint({}) == pytest.approx(0.0)
