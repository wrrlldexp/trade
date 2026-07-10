"""Add tick_interval_sec to grids table.

Revision ID: 20260517_0004
Revises: 20260514_0003
Create Date: 2026-05-17 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260517_0004"
down_revision: str | None = "20260514_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "grids",
        sa.Column("tick_interval_sec", sa.Numeric(5, 2), nullable=False, server_default="1.0"),
    )


def downgrade() -> None:
    op.drop_column("grids", "tick_interval_sec")
