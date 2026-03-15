"""
src/llm/cerebras.py  (AM-17)

Cerebras API client — Llama 3.3 70B (batch/classification) and Llama 3.1 8B (monitoring/heartbeats).
Includes a circuit breaker: after 3 consecutive failures, raises immediately without hitting the API.
Never called directly by agents; always invoked through src/llm/provider.py.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

from src.shared.exceptions import LLMProviderError
from src.shared.schemas import LLMMessage, LLMResponse

_CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"

# Pricing per 1M tokens (USD)
_PRICING: dict[str, dict[str, float]] = {
    "llama3.3-70b": {"input": 0.85, "output": 1.20},
    "llama3.1-8b": {"input": 0.10, "output": 0.10},
}


def _compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = _PRICING.get(model, {"input": 0.85, "output": 1.20})
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


# ── Simple circuit breaker ────────────────────────────────────────────────────

@dataclass
class _CircuitBreaker:
    failure_threshold: int = 3
    reset_timeout_seconds: float = 60.0
    _failures: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)

    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self.reset_timeout_seconds:
            # Half-open: allow one attempt through
            self._opened_at = None
            self._failures = 0
            return False
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = time.monotonic()


_circuit_breaker = _CircuitBreaker()


async def call(
    model: str,
    messages: list[LLMMessage],
    *,
    max_tokens: int = 2048,
    api_key: str,
) -> LLMResponse:
    """
    Call the Cerebras inference API (OpenAI-compatible endpoint).

    Args:
        model: Model ID (e.g. "llama3.3-70b")
        messages: Conversation messages.
        max_tokens: Hard cap on output tokens.
        api_key: Cerebras API key (fetched from vault by provider.py).

    Returns:
        LLMResponse with content, token counts, and cost.

    Raises:
        LLMProviderError: on API error or when circuit breaker is open.
    """
    if _circuit_breaker.is_open():
        raise LLMProviderError(
            "cerebras",
            "Circuit breaker is open — too many recent failures. "
            "Retry after the cooldown period.",
        )

    payload = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "max_tokens": max_tokens,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            response = await http.post(
                f"{_CEREBRAS_BASE_URL}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        _circuit_breaker.record_failure()
        raise LLMProviderError("cerebras", f"HTTP {exc.response.status_code}: {exc.response.text}") from exc
    except Exception as exc:
        _circuit_breaker.record_failure()
        raise LLMProviderError("cerebras", str(exc)) from exc

    _circuit_breaker.record_success()

    choice = data["choices"][0]
    content = choice["message"]["content"]
    usage = data.get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)

    return LLMResponse(
        model=model,
        provider="cerebras",
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=_compute_cost(model, input_tokens, output_tokens),
    )
