"""Initial schema — all BrandOS core tables

Revision ID: 0001
Revises:
Create Date: 2026-03-15

Tables created:
  company, agent_config, audit_entry, token_usage,
  ticket, tool_registry, tool_config, specialist_hire
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── company ───────────────────────────────────────────────────────────────
    op.create_table(
        "company",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_wind_down", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("mission", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_company_slug", "company", ["slug"])

    # ── ticket (defined before audit_entry because audit_entry FK → ticket) ──
    op.create_table(
        "ticket",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("company.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("owner_agent_slug", sa.String(64), nullable=True),
        sa.Column("thread", postgresql.JSONB(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column(
            "parent_ticket_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["parent_ticket_id"], ["ticket.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_company_id", "ticket", ["company_id"])
    op.create_index("ix_ticket_status", "ticket", ["status"])

    # ── agent_config ──────────────────────────────────────────────────────────
    op.create_table(
        "agent_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_slug", sa.String(64), nullable=False),
        sa.Column("agent_type", sa.String(32), nullable=False, server_default="standing"),
        sa.Column("model_tier", sa.String(32), nullable=False),
        sa.Column("heartbeat_cron", sa.String(64), nullable=True),
        sa.Column(
            "monthly_budget_cap_usd",
            sa.Numeric(10, 4),
            nullable=False,
            server_default="10.0",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("config_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_config_company_id", "agent_config", ["company_id"])
    op.create_index("ix_agent_config_slug", "agent_config", ["agent_slug"])

    # ── audit_entry (append-only — no UPDATE or DELETE ever) ─────────────────
    op.create_table(
        "audit_entry",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("company.id"),
            nullable=False,
        ),
        sa.Column("agent_slug", sa.String(64), nullable=False),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("goal_ref", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ticket_id"], ["ticket.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_entry_company_id", "audit_entry", ["company_id"])
    op.create_index("ix_audit_entry_agent_slug", "audit_entry", ["agent_slug"])
    op.create_index("ix_audit_entry_created_at", "audit_entry", ["created_at"])

    # ── token_usage ───────────────────────────────────────────────────────────
    op.create_table(
        "token_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("company.id"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_config.id"),
            nullable=False,
        ),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0.0"
        ),
        sa.Column("task_type", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_token_usage_company_id", "token_usage", ["company_id"])
    op.create_index("ix_token_usage_agent_id", "token_usage", ["agent_id"])
    op.create_index("ix_token_usage_created_at", "token_usage", ["created_at"])

    # ── tool_registry ─────────────────────────────────────────────────────────
    op.create_table(
        "tool_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_slug", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "monthly_budget_cap_usd",
            sa.Numeric(10, 4),
            nullable=False,
            server_default="0.0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "tool_slug", name="uq_tool_registry_company_tool"),
    )
    op.create_index("ix_tool_registry_company_id", "tool_registry", ["company_id"])

    # ── tool_config ───────────────────────────────────────────────────────────
    op.create_table(
        "tool_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_slug", sa.String(128), nullable=False),
        sa.Column("config_json", postgresql.JSONB(), nullable=False),
        sa.Column("secret_ref", sa.String(512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_config_company_id", "tool_config", ["company_id"])

    # ── specialist_hire ───────────────────────────────────────────────────────
    op.create_table(
        "specialist_hire",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("company.id"),
            nullable=False,
        ),
        sa.Column("specialist_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="proposed"),
        sa.Column("problem_statement", sa.Text(), nullable=False),
        sa.Column("success_criteria", sa.Text(), nullable=False),
        sa.Column(
            "budget_allocated",
            sa.Numeric(10, 4),
            nullable=False,
            server_default="0.0",
        ),
        sa.Column(
            "budget_spent", sa.Numeric(10, 4), nullable=False, server_default="0.0"
        ),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("wound_down_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("proposal_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_specialist_hire_company_id", "specialist_hire", ["company_id"])
    op.create_index("ix_specialist_hire_status", "specialist_hire", ["status"])


def downgrade() -> None:
    # Drop in reverse FK dependency order
    op.drop_table("specialist_hire")
    op.drop_table("tool_config")
    op.drop_table("tool_registry")
    op.drop_table("token_usage")
    op.drop_table("audit_entry")
    op.drop_table("agent_config")
    op.drop_table("ticket")
    op.drop_table("company")
