"""Add start_amount column to grids table.

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa

revision = "20260716_0011"
down_revision = "20260716_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "grids",
        sa.Column(
            "start_amount",
            sa.Numeric(20, 8),
            nullable=False,
            server_default="0",
        ),
    )
    # Backfill: для грид с lot_quote, start_amount = lot_quote * total_levels
    op.execute(
        """
        UPDATE grids
        SET start_amount = lot_quote * (levels_above + levels_below)
        WHERE lot_quote IS NOT NULL AND lot_quote > 0
        """
    )


def downgrade() -> None:
    op.drop_column("grids", "start_amount")
