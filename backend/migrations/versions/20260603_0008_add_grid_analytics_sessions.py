"""Add grid_analytics_sessions table.

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260603_0008"
down_revision = "20260526_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "grid_analytics_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("grid_id", sa.Uuid(), sa.ForeignKey("grids.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settings_before", postgresql.JSONB(), nullable=False),
        sa.Column("settings_after", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_grid_analytics_sessions_grid_id", "grid_analytics_sessions", ["grid_id"])
    op.create_index("ix_grid_analytics_sessions_started_at", "grid_analytics_sessions", ["started_at"])
    op.create_index("ix_grid_analytics_sessions_expires_at", "grid_analytics_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_table("grid_analytics_sessions")
