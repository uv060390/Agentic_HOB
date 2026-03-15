"""
src/shared/models.py

SQLAlchemy ORM models for BrandOS primary database (PostgreSQL 15).

All tables include:
  - id          UUID primary key (server-generated)
  - created_at  timestamp with time zone
  - updated_at  timestamp with time zone (auto-updated)

audit_entry is APPEND-ONLY. No UPDATE or DELETE operations ever.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ─── Base ─────────────────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    pass


# ─── Mixins ───────────────────────────────────────────────────────────────────


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ─── company ──────────────────────────────────────────────────────────────────


class Company(TimestampMixin, Base):
    """
    Represents a brand in the house of brands (e.g. AIM, LembasMax).
    Brand isolation is enforced at vault and registry layers; every
    agent and tool references a company_id.
    """

    __tablename__ = "company"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # wind_down mode: agents reduce scope to liquidation tasks
    is_wind_down: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mission: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    agent_configs: Mapped[list["AgentConfig"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    audit_entries: Mapped[list["AuditEntry"]] = relationship(back_populates="company")
    token_usages: Mapped[list["TokenUsage"]] = relationship(back_populates="company")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="company")
    tool_registry_entries: Mapped[list["ToolRegistry"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    tool_configs: Mapped[list["ToolConfig"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    specialist_hires: Mapped[list["SpecialistHire"]] = relationship(
        back_populates="company"
    )

    def __repr__(self) -> str:
        return f"<Company slug={self.slug!r} active={self.is_active}>"


# ─── agent_config ─────────────────────────────────────────────────────────────


class AgentConfig(TimestampMixin, Base):
    """
    Configuration for a single agent instance within a brand.
    Agent templates (standing + specialist) are instantiated per brand
    from these rows — brand-specific config lives here, not in code.
    """

    __tablename__ = "agent_config"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id", ondelete="CASCADE"), nullable=False
    )
    agent_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    # standing | specialist
    agent_type: Mapped[str] = mapped_column(String(32), nullable=False, default="standing")
    model_tier: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # strategy | creative | batch | monitoring
    # Heartbeat cron expression (e.g. "0 9 * * 1" = Monday 9am)
    heartbeat_cron: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Monthly hard budget cap in USD
    monthly_budget_cap_usd: Mapped[float] = mapped_column(
        Numeric(10, 4), nullable=False, default=10.0
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    company: Mapped["Company"] = relationship(back_populates="agent_configs")

    def __repr__(self) -> str:
        return f"<AgentConfig slug={self.agent_slug!r} company={self.company_id}>"


# ─── audit_entry ──────────────────────────────────────────────────────────────


class AuditEntry(TimestampMixin, Base):
    """
    Append-only audit log. Every agent action that changes state writes
    one row here before returning.

    IMPORTANT: No UPDATE or DELETE operations are ever permitted on this table.
    Migrations may add columns but must never modify existing rows.
    """

    __tablename__ = "audit_entry"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=False
    )
    agent_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    # Structured payload of what changed
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # ticket_id this entry belongs to, if any
    ticket_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ticket.id"), nullable=True
    )
    # Trace: which task/project/mission this action serves
    goal_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    company: Mapped["Company"] = relationship(back_populates="audit_entries")
    ticket: Mapped[Optional["Ticket"]] = relationship(back_populates="audit_entries")

    def __repr__(self) -> str:
        return f"<AuditEntry agent={self.agent_slug!r} action={self.action!r}>"


# ─── token_usage ──────────────────────────────────────────────────────────────


class TokenUsage(TimestampMixin, Base):
    """
    Tracks LLM token consumption per agent invocation.
    Used by the budget enforcer to enforce per-agent monthly hard limits.
    """

    __tablename__ = "token_usage"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_config.id"), nullable=False
    )
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)  # anthropic | cerebras
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, default=0.0)
    task_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    company: Mapped["Company"] = relationship(back_populates="token_usages")

    def __repr__(self) -> str:
        return (
            f"<TokenUsage agent={self.agent_id} model={self.model!r} "
            f"cost=${self.cost_usd:.6f}>"
        )


# ─── ticket ───────────────────────────────────────────────────────────────────


class Ticket(TimestampMixin, Base):
    """
    Threaded conversation and decision tracking for agent tasks.
    Agents create a ticket when starting a task and update it as work progresses.
    Long-running tasks return a ticket_id immediately; results are polled here.
    """

    __tablename__ = "ticket"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # open | in_progress | resolved | closed
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    # Which agent owns this ticket
    owner_agent_slug: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Threaded messages as JSONB array [{role, content, timestamp}]
    thread: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Parent ticket for sub-tasks
    parent_ticket_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ticket.id"), nullable=True
    )

    company: Mapped["Company"] = relationship(back_populates="tickets")
    audit_entries: Mapped[list["AuditEntry"]] = relationship(back_populates="ticket")

    def __repr__(self) -> str:
        return f"<Ticket id={self.id} status={self.status!r} title={self.title[:40]!r}>"


# ─── tool_registry ────────────────────────────────────────────────────────────


class ToolRegistry(TimestampMixin, Base):
    """
    Maps which tools are active for which brand.
    A tool module existing in code does NOT make it available to agents —
    it must have an active entry here. Tool activation is a DB insert,
    not a code change.
    """

    __tablename__ = "tool_registry"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id", ondelete="CASCADE"), nullable=False
    )
    tool_slug: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Monthly budget cap for this tool's external API costs (separate from LLM budget)
    monthly_budget_cap_usd: Mapped[float] = mapped_column(
        Numeric(10, 4), nullable=False, default=0.0
    )

    company: Mapped["Company"] = relationship(back_populates="tool_registry_entries")

    def __repr__(self) -> str:
        return f"<ToolRegistry tool={self.tool_slug!r} active={self.is_active}>"


# ─── tool_config ──────────────────────────────────────────────────────────────


class ToolConfig(TimestampMixin, Base):
    """
    Stores custom API adapter configs per brand.
    Used by src/tools/custom_adapter.py to call arbitrary REST APIs
    without writing a dedicated tool module.
    """

    __tablename__ = "tool_config"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id", ondelete="CASCADE"), nullable=False
    )
    tool_slug: Mapped[str] = mapped_column(String(128), nullable=False)
    # Full adapter config: base_url, auth_type, endpoints, etc.
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Infisical path to the credential (e.g. "aim/crm_token")
    secret_ref: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    company: Mapped["Company"] = relationship(back_populates="tool_configs")

    def __repr__(self) -> str:
        return f"<ToolConfig tool={self.tool_slug!r} company={self.company_id}>"


# ─── specialist_hire ──────────────────────────────────────────────────────────


class SpecialistHire(TimestampMixin, Base):
    """
    Tracks the full lifecycle of on-demand specialist agent hires.
    No specialist is instantiated without founder approval via governance.

    Lifecycle: proposed → approved → active → wound_down
    """

    __tablename__ = "specialist_hire"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id"), nullable=False
    )
    # e.g. data_scientist | engineer | data_analyst | seo_aeo | growth_hacker
    specialist_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # proposed | approved | active | wound_down | rejected
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed")
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False)
    success_criteria: Mapped[str] = mapped_column(Text, nullable=False)
    # Budget allocation in USD
    budget_allocated: Mapped[float] = mapped_column(
        Numeric(10, 4), nullable=False, default=0.0
    )
    budget_spent: Mapped[float] = mapped_column(
        Numeric(10, 4), nullable=False, default=0.0
    )
    # Who approved (founder identifier or "auto" if governance override)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    activated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    wound_down_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Hiring manager's proposal detail
    proposal_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    company: Mapped["Company"] = relationship(back_populates="specialist_hires")

    def __repr__(self) -> str:
        return (
            f"<SpecialistHire type={self.specialist_type!r} status={self.status!r}>"
        )
