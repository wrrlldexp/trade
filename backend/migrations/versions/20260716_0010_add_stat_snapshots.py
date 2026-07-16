"""Add grid_stat_snapshots and account_stat_snapshots tables.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa

revision = "20260716_0010"
down_revision = "20260712_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "grid_stat_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("grid_id", sa.Uuid(), nullable=False),
        sa.Column(
            "time",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("course", sa.Numeric(20, 8), nullable=False),
        sa.Column("profit_math", sa.Numeric(20, 8), nullable=False),
        sa.Column("net_asset", sa.Numeric(20, 8), nullable=False),
        sa.Column("net_asset_sag", sa.Numeric(20, 8), nullable=False),
        sa.Column("profit_drift", sa.Numeric(20, 8), nullable=False),
        sa.Column("total_trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("placed_orders", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["grid_id"], ["grids.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_grid_stat_snapshots_grid_id_time",
        "grid_stat_snapshots",
        ["grid_id", "time"],
    )
    op.create_index("ix_grid_stat_snapshots_time", "grid_stat_snapshots", ["time"])

    op.create_table(
        "account_stat_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column(
            "time",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("net_asset", sa.Numeric(20, 8), nullable=False),
        sa.Column("base_balance", sa.Numeric(20, 8), nullable=False),
        sa.Column("quote_balance", sa.Numeric(20, 8), nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["exchange_accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_account_stat_snapshots_account_id_time",
        "account_stat_snapshots",
        ["account_id", "time"],
    )
    op.create_index(
        "ix_account_stat_snapshots_time", "account_stat_snapshots", ["time"]
    )


def downgrade() -> None:
    op.drop_index("ix_account_stat_snapshots_time")
    op.drop_index("ix_account_stat_snapshots_account_id_time")
    op.drop_table("account_stat_snapshots")
    op.drop_index("ix_grid_stat_snapshots_time")
    op.drop_index("ix_grid_stat_snapshots_grid_id_time")
    op.drop_table("grid_stat_snapshots")
