"""Week 2 column additions — agent lifecycle fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-15

Adds:
  agent_config: agent_template, reports_to_slug, is_paused, is_specialist
  audit_entry:  is_rolled_back
  ticket:       description, task_type, resolution, project_name
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── agent_config ──────────────────────────────────────────────────────────
    op.add_column(
        "agent_config",
        sa.Column("agent_template", sa.String(64), nullable=True),
    )
    op.add_column(
        "agent_config",
        sa.Column("reports_to_slug", sa.String(64), nullable=True),
    )
    op.add_column(
        "agent_config",
        sa.Column(
            "is_paused",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "agent_config",
        sa.Column(
            "is_specialist",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # ── audit_entry ───────────────────────────────────────────────────────────
    op.add_column(
        "audit_entry",
        sa.Column(
            "is_rolled_back",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # ── ticket ────────────────────────────────────────────────────────────────
    op.add_column(
        "ticket",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "ticket",
        sa.Column("task_type", sa.String(64), nullable=True),
    )
    op.add_column(
        "ticket",
        sa.Column("resolution", sa.Text(), nullable=True),
    )
    op.add_column(
        "ticket",
        sa.Column("project_name", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    # ── ticket ────────────────────────────────────────────────────────────────
    op.drop_column("ticket", "project_name")
    op.drop_column("ticket", "resolution")
    op.drop_column("ticket", "task_type")
    op.drop_column("ticket", "description")

    # ── audit_entry ───────────────────────────────────────────────────────────
    op.drop_column("audit_entry", "is_rolled_back")

    # ── agent_config ──────────────────────────────────────────────────────────
    op.drop_column("agent_config", "is_specialist")
    op.drop_column("agent_config", "is_paused")
    op.drop_column("agent_config", "reports_to_slug")
    op.drop_column("agent_config", "agent_template")
