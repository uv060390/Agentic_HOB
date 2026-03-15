"""003_orchestration_tables

Add workflow_run, workflow_step, and creative_library tables.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── workflow_run ──────────────────────────────────────────────────────────
    op.create_table(
        "workflow_run",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workflow_name", sa.String(64), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("parent_ticket_id", sa.UUID(), nullable=True),
        sa.Column("step_outputs", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── workflow_step ─────────────────────────────────────────────────────────
    op.create_table(
        "workflow_step",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("agent_template", sa.String(64), nullable=False),
        sa.Column("task_subtype", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_run.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── creative_library ──────────────────────────────────────────────────────
    op.create_table(
        "creative_library",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_slug", sa.String(64), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),          # competitor | original
        sa.Column("competitor_brand", sa.String(128), nullable=True),
        sa.Column("predicted_ctr", sa.Numeric(8, 4), nullable=True),
        sa.Column("actual_ctr", sa.Numeric(8, 4), nullable=True),    # updated retroactively
        sa.Column("creative_type", sa.String(32), nullable=False, server_default="image"),
        sa.Column("file_url", sa.Text(), nullable=False),
        sa.Column("created_by_agent", sa.String(64), nullable=False),
        sa.Column("workflow_run_id", sa.UUID(), nullable=True),
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
    op.create_index("ix_creative_library_brand_slug", "creative_library", ["brand_slug"])
    op.create_index("ix_creative_library_source", "creative_library", ["source"])


def downgrade() -> None:
    op.drop_index("ix_creative_library_source", "creative_library")
    op.drop_index("ix_creative_library_brand_slug", "creative_library")
    op.drop_table("creative_library")
    op.drop_table("workflow_step")
    op.drop_table("workflow_run")
