"""Add grid_activity_logs table.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260712_0009"
down_revision = "20260603_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "grid_activity_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("grid_id", sa.Uuid(), nullable=False),
        sa.Column("event", sa.String(50), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["grid_id"], ["grids.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_grid_activity_logs_grid_id", "grid_activity_logs", ["grid_id"])
    op.create_index("ix_grid_activity_logs_event", "grid_activity_logs", ["event"])
    op.create_index("ix_grid_activity_logs_created_at", "grid_activity_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_grid_activity_logs_created_at")
    op.drop_index("ix_grid_activity_logs_event")
    op.drop_index("ix_grid_activity_logs_grid_id")
    op.drop_table("grid_activity_logs")
