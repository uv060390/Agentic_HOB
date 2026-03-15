"""
tests/unit/test_tool_registry.py

Tests for tool registry, tool isolation, and custom adapter.
"""

import pytest
from src.tools.base_tool import BaseTool
from src.tools.ads.meta_ads import MetaAdsTool
from src.tools.ads.google_ads import GoogleAdsTool
from src.tools.ads.amazon_ads import AmazonAdsTool
from src.tools.commerce.shopify import ShopifyTool
from src.tools.commerce.amazon import AmazonSellerTool
from src.tools.commerce.blinkit import BlinkitTool
from src.tools.commerce.lovable_shopify import LovableShopifyTool
from src.tools.commerce.lovable_prompt_builder import build_lovable_prompt
from src.tools.llm_as_tool.chatgpt import ChatGPTTool
from src.tools.llm_as_tool.perplexity import PerplexityTool
from src.tools.comms.gmail import GmailTool
from src.tools.comms.whatsapp import WhatsAppTool
from src.tools.logistics.shiprocket import ShiprocketTool
from src.tools.logistics.delhivery import DelhiveryTool
from src.tools.compliance.fssai import FSSAITool
from src.tools.data.supabase_client import SupabaseTool
from src.tools.data.d2c_benchmarks import D2CBenchmarksTool


class TestBaseTool:
    def test_base_tool_is_abstract(self):
        with pytest.raises(TypeError):
            BaseTool("aim")  # type: ignore

    def test_tool_slug_on_subclass(self):
        tool = MetaAdsTool("aim")
        assert tool.slug == "meta_ads"
        assert tool.company_slug == "aim"


class TestAdTools:
    @pytest.mark.asyncio
    async def test_meta_ads_get_campaigns(self):
        tool = MetaAdsTool("aim")
        result = await tool.execute("get_campaigns", {})
        assert result["ok"] is True
        assert "campaigns" in result["data"]

    @pytest.mark.asyncio
    async def test_meta_ads_unknown_action(self):
        tool = MetaAdsTool("aim")
        result = await tool.execute("unknown", {})
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_google_ads_get_campaigns(self):
        tool = GoogleAdsTool("aim")
        result = await tool.execute("get_campaigns", {})
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_amazon_ads_get_sponsored(self):
        tool = AmazonAdsTool("aim")
        result = await tool.execute("get_sponsored_products", {})
        assert result["ok"] is True


class TestCommerceTools:
    @pytest.mark.asyncio
    async def test_shopify_get_products(self):
        tool = ShopifyTool("aim")
        result = await tool.execute("get_products", {})
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_amazon_seller_get_listings(self):
        tool = AmazonSellerTool("aim")
        result = await tool.execute("get_listings", {})
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_blinkit_get_listings(self):
        tool = BlinkitTool("aim")
        result = await tool.execute("get_listings", {})
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_lovable_build_page(self):
        tool = LovableShopifyTool("aim")
        result = await tool.execute("build_page", {"page_type": "landing"})
        assert result["ok"] is True
        assert "page_url" in result["data"]

    def test_lovable_prompt_builder(self):
        prompt = build_lovable_prompt(
            brand_slug="aim",
            page_type="landing",
            brand_identity={"name": "AIM", "colors": {"primary": "#FF0000"}},
        )
        assert "AIM" in prompt
        assert "landing" in prompt
        assert "mobile-responsive" in prompt


class TestLLMAsToolTools:
    @pytest.mark.asyncio
    async def test_chatgpt_visibility(self):
        tool = ChatGPTTool("aim")
        result = await tool.execute("test_brand_visibility", {"query": "best protein powder India"})
        assert result["ok"] is True
        assert "brand_mentioned" in result["data"]

    @pytest.mark.asyncio
    async def test_perplexity_visibility(self):
        tool = PerplexityTool("aim")
        result = await tool.execute("test_brand_visibility", {"query": "best protein powder India"})
        assert result["ok"] is True
        assert "brand_mentioned" in result["data"]


class TestCommsTools:
    @pytest.mark.asyncio
    async def test_gmail_send(self):
        tool = GmailTool("aim")
        result = await tool.execute("send_email", {"to": "supplier@example.com"})
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_whatsapp_send(self):
        tool = WhatsAppTool("aim")
        result = await tool.execute("send_message", {"to": "+919999999999"})
        assert result["ok"] is True


class TestLogisticsTools:
    @pytest.mark.asyncio
    async def test_shiprocket_create(self):
        tool = ShiprocketTool("aim")
        result = await tool.execute("create_shipment", {"order_id": "ORD-001"})
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_delhivery_pincode(self):
        tool = DelhiveryTool("aim")
        result = await tool.execute("check_pincode", {"pincode": "110001"})
        assert result["ok"] is True
        assert result["data"]["serviceable"] is True


class TestComplianceTools:
    @pytest.mark.asyncio
    async def test_fssai_renewal(self):
        tool = FSSAITool("aim")
        result = await tool.execute("check_renewal_status", {})
        assert result["ok"] is True


class TestDataTools:
    @pytest.mark.asyncio
    async def test_supabase_select(self):
        tool = SupabaseTool("aim")
        result = await tool.execute("select", {"table": "products"})
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_d2c_benchmarks(self):
        tool = D2CBenchmarksTool("aim")
        result = await tool.execute("get_benchmarks", {"category": "personal_care"})
        assert result["ok"] is True
        assert "benchmarks" in result["data"]

    @pytest.mark.asyncio
    async def test_d2c_compare_metric(self):
        tool = D2CBenchmarksTool("aim")
        result = await tool.execute("compare_metric", {
            "category": "personal_care",
            "metric": "cac_inr",
            "value": 400,
        })
        assert result["ok"] is True
        assert result["data"]["position"] in ("above_median", "below_median")

    @pytest.mark.asyncio
    async def test_d2c_list_categories(self):
        tool = D2CBenchmarksTool("aim")
        result = await tool.execute("list_categories", {})
        assert result["ok"] is True
        assert "personal_care" in result["data"]["categories"]
