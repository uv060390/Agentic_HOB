"""
tests/unit/test_intent_router.py

Tests for intent resolution and routing.
"""

import pytest
from src.gateway.intent_router import resolve_intent


class TestIntentResolution:
    def test_default_routes_to_ceo(self):
        result = resolve_intent("hello")
        assert result["agent_template"] == "ceo"
        assert result["brand_slug"] == "aim"

    def test_aim_brand_detection(self):
        result = resolve_intent("how's aim doing?")
        assert result["brand_slug"] == "aim"
        assert result["agent_template"] == "ceo"
        assert result["task_subtype"] == "weekly_synthesis"

    def test_lembasmax_brand_detection(self):
        result = resolve_intent("lembasmax unit economics report")
        assert result["brand_slug"] == "lembasmax"
        assert result["agent_template"] == "finance"

    def test_finance_intent(self):
        result = resolve_intent("show me the P&L")
        assert result["agent_template"] == "finance"

    def test_campaign_intent(self):
        result = resolve_intent("write a campaign brief")
        assert result["agent_template"] == "cmo"

    def test_creative_intent(self):
        result = resolve_intent("create some ad copy")
        assert result["agent_template"] == "creative"

    def test_performance_intent(self):
        result = resolve_intent("what's our roas this week?")
        assert result["agent_template"] == "performance"

    def test_scout_intent(self):
        result = resolve_intent("scan the ad library for our competition")
        assert result["agent_template"] == "scout"

    def test_ops_intent(self):
        result = resolve_intent("what's the fssai renewal date?")
        assert result["agent_template"] == "ops"

    def test_seo_intent(self):
        result = resolve_intent("test our aeo visibility")
        assert result["agent_template"] == "seo_aeo"

    def test_growth_intent(self):
        result = resolve_intent("design a referral program")
        assert result["agent_template"] == "growth_hacker"

    def test_portfolio_intent(self):
        result = resolve_intent("show all brands consolidated view")
        assert result["agent_template"] == "portfolio_cfo"

    def test_bd_intent(self):
        result = resolve_intent("find a new brand to acquire")
        assert result["agent_template"] == "bd"

    def test_status_maps_to_ceo(self):
        result = resolve_intent("give me a status update")
        assert result["agent_template"] == "ceo"
        assert result["task_subtype"] == "weekly_synthesis"
