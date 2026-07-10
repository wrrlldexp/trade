"""Add lot_quote field for fiat-denominated lot sizing."""

from alembic import op
import sqlalchemy as sa

revision = "20260526_0007"
down_revision = "20260525_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("grids", sa.Column("lot_quote", sa.Numeric(20, 8), nullable=True))


def downgrade() -> None:
    op.drop_column("grids", "lot_quote")
