"""
src/shared/schemas.py

Shared Pydantic request/response schemas used across Gateway and agent layers.
All API responses use the standard envelope: { "ok": bool, "data": ..., "error": ... }
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ── Standard API envelope ─────────────────────────────────────────────────────


class ApiResponse(BaseModel, Generic[T]):
    ok: bool
    data: T | None = None
    error: str | None = None

    @classmethod
    def success(cls, data: T) -> "ApiResponse[T]":
        return cls(ok=True, data=data)

    @classmethod
    def failure(cls, error: str) -> "ApiResponse[Any]":  # type: ignore[override]
        return cls(ok=False, error=error)  # type: ignore[return-value]


# ── LLM ──────────────────────────────────────────────────────────────────────


class LLMMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class LLMRequest(BaseModel):
    task_type: str  # strategy | creative | batch | monitoring
    messages: list[LLMMessage]
    agent_id: str
    company_id: str
    max_tokens: int = Field(default=2048, ge=1, le=8192)


class LLMResponse(BaseModel):
    model: str
    provider: str
    content: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


# ── Audit ─────────────────────────────────────────────────────────────────────


class AuditEntryCreate(BaseModel):
    company_id: str
    agent_slug: str
    action: str
    payload: dict[str, Any] | None = None
    ticket_id: str | None = None
    goal_ref: str | None = None


# ── Health ────────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = "ok"
    env: str
    db: str = "unknown"
