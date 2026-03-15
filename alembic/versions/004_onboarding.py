"""004_onboarding

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-15

Adds onboarding_session table for the conversational setup wizard.
Founders who message the bot before their brand is configured are
walked through a persistent, resumable onboarding flow.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "onboarding_session",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # The Telegram chat_id (as string) or WhatsApp phone number.
        # One active session per founder enforced at application layer.
        sa.Column("founder_id", sa.String(255), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),   # "telegram" | "whatsapp"
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="in_progress",
        ),  # "in_progress" | "complete" | "abandoned"
        sa.Column(
            "current_step_id",
            sa.String(64),
            nullable=False,
            server_default="welcome",
        ),
        # Ordered list of completed step IDs — append-only during the session.
        sa.Column(
            "completed_steps",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        # Non-sensitive config collected so far (brand name, slug, category,
        # mission, supabase_url, selected_tools, budget_caps, brand_colors,
        # product_image_urls). NEVER contains API keys or passwords.
        sa.Column(
            "collected_config",
            sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
        # FIFO queue of tool credential step IDs, populated when the founder
        # selects tools at tool_selection step. Consumed left-to-right.
        sa.Column(
            "pending_tool_steps",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        # Set once auto_provision completes successfully.
        sa.Column("company_id", sa.UUID(as_uuid=True), nullable=True),
        # Last validation error message shown to the founder. Overwritten on
        # each validation failure; cleared on step advance.
        sa.Column("error_message", sa.Text(), nullable=True),
        # Used for abandonment detection (no activity for 7 days → abandoned).
        sa.Column(
            "last_message_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_onboarding_session_founder_id",
        "onboarding_session",
        ["founder_id"],
    )
    op.create_index(
        "ix_onboarding_session_status",
        "onboarding_session",
        ["status"],
    )
    op.create_index(
        "ix_onboarding_session_channel",
        "onboarding_session",
        ["channel"],
    )


def downgrade() -> None:
    op.drop_index("ix_onboarding_session_channel", table_name="onboarding_session")
    op.drop_index("ix_onboarding_session_status", table_name="onboarding_session")
    op.drop_index("ix_onboarding_session_founder_id", table_name="onboarding_session")
    op.drop_table("onboarding_session")
