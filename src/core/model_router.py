"""
src/core/model_router.py  (AM-18)

Maps task types to model IDs and providers.
Agents never select their own model — the router decides based on task type.
Called by src/llm/provider.py before every LLM invocation.

Task type → model mapping (from CLAUDE.md):
  strategy    → claude-opus-4-6     (Anthropic)
  creative    → claude-sonnet-4-6   (Anthropic)
  batch       → llama3.3-70b        (Cerebras)
  monitoring  → llama3.1-8b         (Cerebras)
"""

from __future__ import annotations

from dataclasses import dataclass

from src.shared.exceptions import ModelRouterError


@dataclass(frozen=True)
class ModelRoute:
    model: str
    provider: str  # "anthropic" | "cerebras"


_ROUTES: dict[str, ModelRoute] = {
    "strategy": ModelRoute(model="claude-opus-4-6", provider="anthropic"),
    "creative": ModelRoute(model="claude-sonnet-4-6", provider="anthropic"),
    "batch": ModelRoute(model="llama3.3-70b", provider="cerebras"),
    "monitoring": ModelRoute(model="llama3.1-8b", provider="cerebras"),
}


def route(task_type: str) -> ModelRoute:
    """
    Return the ModelRoute for a given task type.

    Args:
        task_type: One of "strategy", "creative", "batch", "monitoring".

    Returns:
        ModelRoute(model, provider)

    Raises:
        ModelRouterError: if task_type is not in the routing table.
    """
    result = _ROUTES.get(task_type)
    if result is None:
        raise ModelRouterError(task_type)
    return result


def supported_task_types() -> list[str]:
    """Return all registered task types."""
    return list(_ROUTES.keys())
