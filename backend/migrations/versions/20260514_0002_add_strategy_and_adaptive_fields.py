"""Add strategy type, adaptive fields, and legacy order columns.

Revision ID: 20260514_0002
Revises: 20260408_0001
Create Date: 2026-05-14 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260514_0002"
down_revision: str | None = "20260408_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- New enums ---
    op.execute("DO $$ BEGIN CREATE TYPE strategy_type AS ENUM ('simple','capitalization','reverse','reverse_cap','adaptive','adaptive_cap'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    from sqlalchemy.dialects import postgresql
    strategy_type = postgresql.ENUM("simple", "capitalization", "reverse", "reverse_cap", "adaptive", "adaptive_cap", name="strategy_type", create_type=False)

    # --- Add missing value to existing enums ---
    # order_status: add 'wait'
    op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'wait'")
    # trade_event_type: add 'adaptive_shift'
    op.execute("ALTER TYPE trade_event_type ADD VALUE IF NOT EXISTS 'adaptive_shift'")

    # --- grids: add strategy and adaptive columns ---
    op.add_column("grids", sa.Column(
        "strategy", strategy_type, nullable=False, server_default="simple",
    ))
    op.add_column("grids", sa.Column(
        "adaptive_timer_sec", sa.Integer(), nullable=False, server_default="15",
    ))
    op.add_column("grids", sa.Column(
        "adaptive_top_order_idx", sa.Integer(), nullable=True,
    ))
    op.add_column("grids", sa.Column(
        "adaptive_bottom_order_idx", sa.Integer(), nullable=True,
    ))
    op.add_column("grids", sa.Column(
        "prepay_base", sa.Numeric(20, 8), nullable=False, server_default="0",
    ))
    op.add_column("grids", sa.Column(
        "prepay_quote", sa.Numeric(20, 8), nullable=False, server_default="0",
    ))
    op.add_column("grids", sa.Column(
        "prepay_amount", sa.Numeric(20, 8), nullable=False, server_default="0",
    ))
    op.add_column("grids", sa.Column(
        "prepay_base_tail", sa.Numeric(20, 8), nullable=False, server_default="0",
    ))
    op.add_column("grids", sa.Column(
        "prepay_quote_tail", sa.Numeric(20, 8), nullable=False, server_default="0",
    ))

    # --- grid_orders: add legacy columns ---
    op.add_column("grid_orders", sa.Column(
        "grid_index", sa.Integer(), nullable=False, server_default="0",
    ))
    op.add_column("grid_orders", sa.Column(
        "price_sell", sa.Numeric(20, 8), nullable=False, server_default="0",
    ))
    op.add_column("grid_orders", sa.Column(
        "prepay", sa.Numeric(20, 8), nullable=False, server_default="0",
    ))
    op.add_column("grid_orders", sa.Column(
        "re_buy", sa.Boolean(), nullable=False, server_default=sa.text("false"),
    ))
    op.add_column("grid_orders", sa.Column(
        "re_sell", sa.Boolean(), nullable=False, server_default=sa.text("false"),
    ))
    op.add_column("grid_orders", sa.Column(
        "profit", sa.Numeric(20, 8), nullable=False, server_default="0",
    ))
    op.add_column("grid_orders", sa.Column(
        "count_complete", sa.Integer(), nullable=False, server_default="0",
    ))


def downgrade() -> None:
    # --- grid_orders ---
    op.drop_column("grid_orders", "count_complete")
    op.drop_column("grid_orders", "profit")
    op.drop_column("grid_orders", "re_sell")
    op.drop_column("grid_orders", "re_buy")
    op.drop_column("grid_orders", "prepay")
    op.drop_column("grid_orders", "price_sell")
    op.drop_column("grid_orders", "grid_index")

    # --- grids ---
    op.drop_column("grids", "prepay_quote_tail")
    op.drop_column("grids", "prepay_base_tail")
    op.drop_column("grids", "prepay_amount")
    op.drop_column("grids", "prepay_quote")
    op.drop_column("grids", "prepay_base")
    op.drop_column("grids", "adaptive_bottom_order_idx")
    op.drop_column("grids", "adaptive_top_order_idx")
    op.drop_column("grids", "adaptive_timer_sec")
    op.drop_column("grids", "strategy")

    op.execute("DROP TYPE IF EXISTS strategy_type")
