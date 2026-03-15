"""
src/llm/anthropic.py  (AM-16)

Anthropic API client — Claude Opus (strategy/synthesis) and Claude Sonnet (creative/analysis).
Never called directly by agents; always invoked through src/llm/provider.py.
"""

from __future__ import annotations

import anthropic

from src.shared.exceptions import LLMProviderError
from src.shared.schemas import LLMMessage, LLMResponse

# Pricing per 1M tokens (USD) — used by budget enforcer
_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-6": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
}


def _compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = _PRICING.get(model, {"input": 15.0, "output": 75.0})
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


async def call(
    model: str,
    messages: list[LLMMessage],
    *,
    max_tokens: int = 2048,
    api_key: str,
) -> LLMResponse:
    """
    Call the Anthropic API.

    Args:
        model: Model ID (e.g. "claude-opus-4-6")
        messages: Conversation messages; system messages are extracted automatically.
        max_tokens: Hard cap on output tokens.
        api_key: Anthropic API key (fetched from vault by provider.py).

    Returns:
        LLMResponse with content, token counts, and cost.

    Raises:
        LLMProviderError: on any Anthropic API error.
    """
    client = anthropic.AsyncAnthropic(api_key=api_key)

    # Extract system message if present
    system_parts: list[str] = []
    user_messages: list[dict[str, str]] = []

    for msg in messages:
        if msg.role == "system":
            system_parts.append(msg.content)
        else:
            user_messages.append({"role": msg.role, "content": msg.content})

    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": user_messages,
    }
    if system_parts:
        kwargs["system"] = "\n".join(system_parts)

    try:
        response = await client.messages.create(**kwargs)  # type: ignore[arg-type]
    except anthropic.APIError as exc:
        raise LLMProviderError("anthropic", str(exc)) from exc

    content = next(
        (block.text for block in response.content if hasattr(block, "text")), ""  # type: ignore[union-attr]
    )
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    return LLMResponse(
        model=model,
        provider="anthropic",
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=_compute_cost(model, input_tokens, output_tokens),
    )
