"""
src/tools/commerce/lovable_prompt_builder.py  (AM-96)

Assembles brand-aware prompts for the Lovable AI storefront builder.
Takes brand identity, products, and page type as inputs and produces
a structured prompt optimised for Lovable's page generation API.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_lovable_prompt(
    brand_slug: str,
    page_type: str,
    brand_identity: dict[str, Any] | None = None,
    products: list[dict[str, Any]] | None = None,
    custom_instructions: str = "",
) -> str:
    """
    Assemble a brand-aware prompt for Lovable AI.

    Args:
        brand_slug:         Brand identifier.
        page_type:          "landing" | "product" | "collection" | "about"
        brand_identity:     Dict with brand colours, fonts, tone, logo URL.
        products:           List of product dicts for product/collection pages.
        custom_instructions: Additional instructions from the agent.

    Returns:
        Formatted prompt string for Lovable's API.
    """
    identity = brand_identity or {}
    brand_name = identity.get("name", brand_slug.upper())
    colors = identity.get("colors", {"primary": "#000000", "secondary": "#FFFFFF"})
    tone = identity.get("tone", "professional, modern, clean")

    prompt_parts = [
        f"Create a {page_type} page for the brand '{brand_name}'.",
        f"Brand tone: {tone}.",
        f"Primary color: {colors.get('primary', '#000000')}, "
        f"Secondary color: {colors.get('secondary', '#FFFFFF')}.",
    ]

    if page_type in ("product", "collection") and products:
        product_names = [p.get("name", "Product") for p in products[:5]]
        prompt_parts.append(f"Featured products: {', '.join(product_names)}.")

    if custom_instructions:
        prompt_parts.append(f"Additional requirements: {custom_instructions}")

    prompt_parts.append(
        "The page must be mobile-responsive, fast-loading, and optimised for conversions. "
        "Include clear CTAs and trust signals."
    )

    prompt = " ".join(prompt_parts)
    logger.info("LovablePromptBuilder | brand=%s page_type=%s len=%d", brand_slug, page_type, len(prompt))
    return prompt
