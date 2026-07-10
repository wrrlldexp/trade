"""Add auto_convert_to and unconverted_pnl to grids.

Revision ID: 20260525_0006
Revises: 20260517_0005
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa

revision = "20260525_0006"
down_revision = "20260517_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("grids", sa.Column("auto_convert_to", sa.String(10), nullable=True))
    op.add_column(
        "grids",
        sa.Column("unconverted_pnl", sa.Numeric(20, 8), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("grids", "unconverted_pnl")
    op.drop_column("grids", "auto_convert_to")
