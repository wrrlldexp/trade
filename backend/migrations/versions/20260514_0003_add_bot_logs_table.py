"""Add bot_logs table for bot monitoring.

Revision ID: 20260514_0003
Revises: 20260514_0002
Create Date: 2026-05-14 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260514_0003"
down_revision: str | None = "20260514_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DO $$ BEGIN CREATE TYPE log_level AS ENUM ('info','warning','error','critical'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    from sqlalchemy.dialects import postgresql
    log_level = postgresql.ENUM("info", "warning", "error", "critical", name="log_level", create_type=False)

    op.create_table(
        "bot_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("level", log_level, nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("source", sa.String(500), nullable=True),
        sa.Column("grid_id", sa.Uuid(), nullable=True),
        sa.Column("traceback", sa.String(10000), nullable=True),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB, "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["grid_id"], ["grids.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bot_logs_level", "bot_logs", ["level"])
    op.create_index("ix_bot_logs_grid_id", "bot_logs", ["grid_id"])
    op.create_index("ix_bot_logs_created_at", "bot_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("bot_logs")
    op.execute("DROP TYPE IF EXISTS log_level")
