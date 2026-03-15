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


# ── Agent task / result / report ──────────────────────────────────────────────


class AgentTask(BaseModel):
    task_subtype: str
    context: dict[str, Any] = Field(default_factory=dict)
    ticket_id: str | None = None


class AgentResult(BaseModel):
    success: bool
    output: str
    ticket_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentReport(BaseModel):
    agent_id: str
    company_id: str
    last_run_at: str | None = None
    open_tickets_count: int = 0
    status: str = "idle"


# ── Goal ancestry ─────────────────────────────────────────────────────────────


class GoalAncestry(BaseModel):
    ticket_id: str
    ticket_summary: str
    project_name: str | None = None
    company_slug: str
    company_name: str
    mission: str | None = None


# ── Specialist hire ───────────────────────────────────────────────────────────


class SpecialistHireSchema(BaseModel):
    id: str
    company_slug: str
    specialist_type: str
    status: str
    problem_statement: str
    success_criteria: str
    budget_allocated: float
    budget_spent: float
    approved_by: str | None = None
    activated_at: str | None = None
    wound_down_at: str | None = None


# ── Org chart ─────────────────────────────────────────────────────────────────


class OrgChartSchema(BaseModel):
    company_slug: str
    standing_agents: list[dict] = Field(default_factory=list)
    active_specialists: list[dict] = Field(default_factory=list)
    reporting_lines: dict[str, list[str]] = Field(default_factory=dict)
