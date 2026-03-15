"""
src/llm/provider.py  (AM-15)

Unified LLM interface. All agent LLM calls must go through here.
Responsibilities:
  1. Route the task type to model + provider via model_router
  2. Fetch the correct API key from vault (or sandbox)
  3. Enforce budget (pre-check) via budget_enforcer
  4. Call the appropriate provider client
  5. Record token usage via budget_enforcer

Usage:
    from src.llm.provider import call

    response = await call(
        task_type="strategy",
        messages=[LLMMessage(role="user", content="Analyse our Q1 CAC trends.")],
        agent_id="aim-ceo",
        company_id="aim",
    )
"""

from __future__ import annotations

from src.core import budget_enforcer
from src.core.model_router import route
from src.llm import anthropic as anthropic_client
from src.llm import cerebras as cerebras_client
from src.shared.config import get_settings
from src.shared.exceptions import LLMProviderError, VaultUnavailableError
from src.shared.schemas import LLMMessage, LLMResponse


def _get_api_key(provider: str) -> str:
    """Fetch the API key for the given provider from vault or sandbox."""
    settings = get_settings()
    if settings.use_sandbox_vault:
        from src.vault import sandbox
        key_map = {
            "anthropic": "/shared/anthropic_api_key",
            "cerebras": "/shared/cerebras_api_key",
        }
        path = key_map.get(provider)
        if path is None:
            raise LLMProviderError(provider, f"No key mapping for provider '{provider}'")
        try:
            return sandbox.get_secret(path)
        except Exception:
            # Fall back to settings for local dev
            if provider == "anthropic":
                return settings.anthropic_api_key
            if provider == "cerebras":
                return settings.cerebras_api_key
            raise
    else:
        from src.vault import client as vault
        key_map = {
            "anthropic": "/shared/anthropic_api_key",
            "cerebras": "/shared/cerebras_api_key",
        }
        path = key_map.get(provider)
        if path is None:
            raise LLMProviderError(provider, f"No key mapping for provider '{provider}'")
        return vault.get_secret(path)


async def call(
    task_type: str,
    messages: list[LLMMessage],
    *,
    agent_id: str,
    company_id: str,
    max_tokens: int = 2048,
) -> LLMResponse:
    """
    Route, authorise, call, and record a single LLM invocation.

    Args:
        task_type: "strategy" | "creative" | "batch" | "monitoring"
        messages: Conversation messages (including system prompt if needed).
        agent_id: Slug of the calling agent (for budget tracking).
        company_id: Slug of the brand (for budget tracking + isolation).
        max_tokens: Hard output token cap.

    Returns:
        LLMResponse

    Raises:
        ModelRouterError: unknown task_type
        BudgetExceededError: monthly budget exhausted
        LLMProviderError: provider returned an error
        VaultUnavailableError: cannot reach Infisical
    """
    model_route = route(task_type)

    # Pre-call budget check
    await budget_enforcer.check(agent_id=agent_id, company_id=company_id)

    api_key = _get_api_key(model_route.provider)

    if model_route.provider == "anthropic":
        response = await anthropic_client.call(
            model=model_route.model,
            messages=messages,
            max_tokens=max_tokens,
            api_key=api_key,
        )
    elif model_route.provider == "cerebras":
        response = await cerebras_client.call(
            model=model_route.model,
            messages=messages,
            max_tokens=max_tokens,
            api_key=api_key,
        )
    else:
        raise LLMProviderError(model_route.provider, "Unknown provider in model route")

    # Record usage after successful call
    await budget_enforcer.record(
        agent_id=agent_id,
        company_id=company_id,
        model=response.model,
        provider=response.provider,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=response.cost_usd,
    )

    return response
