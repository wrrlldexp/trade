"""initial schema

Revision ID: 20260408_0001
Revises:
Create Date: 2026-04-08 14:45:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260408_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Создаём enum'ы через raw SQL — asyncpg не поддерживает checkfirst корректно
    op.execute("DO $$ BEGIN CREATE TYPE user_role AS ENUM ('superadmin','admin','viewer'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE grid_mode AS ENUM ('paper','live'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE grid_status AS ENUM ('draft','running','stopped','error'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE order_side AS ENUM ('buy','sell'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE order_status AS ENUM ('pending','placed','filled','cancelled','error'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE trade_event_type AS ENUM ('placed','filled','cancelled','flipped','grid_rebuilt'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")

    # postgresql.ENUM с create_type=False — НЕ пересоздаёт при create_table
    user_role = postgresql.ENUM("superadmin", "admin", "viewer", name="user_role", create_type=False)
    grid_mode = postgresql.ENUM("paper", "live", name="grid_mode", create_type=False)
    grid_status = postgresql.ENUM("draft", "running", "stopped", "error", name="grid_status", create_type=False)
    order_side = postgresql.ENUM("buy", "sell", name="order_side", create_type=False)
    order_status = postgresql.ENUM("pending", "placed", "filled", "cancelled", "error", name="order_status", create_type=False)
    trade_event_type = postgresql.ENUM("placed", "filled", "cancelled", "flipped", "grid_rebuilt", name="trade_event_type", create_type=False)

    op.create_table(
        "users",
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("totp_secret_enc", sa.LargeBinary(), nullable=True),
        sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "user_invites",
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("invited_by_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["invited_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_invites_email"), "user_invites", ["email"], unique=False)
    op.create_index(op.f("ix_user_invites_token"), "user_invites", ["token"], unique=True)

    op.create_table(
        "exchange_accounts",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("exchange", sa.String(50), nullable=False),
        sa.Column("api_key_enc", sa.LargeBinary(), nullable=False),
        sa.Column("api_secret_enc", sa.LargeBinary(), nullable=False),
        sa.Column("is_testnet", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_exchange_accounts_owner_id"), "exchange_accounts", ["owner_id"], unique=False)

    op.create_table(
        "grids",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("mode", grid_mode, nullable=False),
        sa.Column("status", grid_status, nullable=False),
        sa.Column("lot_size", sa.Numeric(20, 8), nullable=False),
        sa.Column("profit_step", sa.Numeric(20, 8), nullable=False),
        sa.Column("grid_step", sa.Numeric(20, 8), nullable=False),
        sa.Column("levels_above", sa.Integer(), nullable=False),
        sa.Column("levels_below", sa.Integer(), nullable=False),
        sa.Column("rebuild_timeout_sec", sa.Integer(), nullable=False),
        sa.Column("last_boundary_hit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("realized_pnl", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["exchange_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_grids_account_id"), "grids", ["account_id"], unique=False)

    op.create_table(
        "grid_orders",
        sa.Column("grid_id", sa.Uuid(), nullable=False),
        sa.Column("side", order_side, nullable=False),
        sa.Column("status", order_status, nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.Column("amount", sa.Numeric(20, 8), nullable=False),
        sa.Column("exchange_order_id", sa.String(100), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["grid_id"], ["grids.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_grid_orders_exchange_order_id"), "grid_orders", ["exchange_order_id"], unique=False)
    op.create_index(op.f("ix_grid_orders_grid_id"), "grid_orders", ["grid_id"], unique=False)
    op.create_index(op.f("ix_grid_orders_status"), "grid_orders", ["status"], unique=False)

    op.create_table(
        "trade_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("grid_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", trade_event_type, nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=True),
        sa.Column("amount", sa.Numeric(20, 8), nullable=True),
        sa.Column("pnl_delta", sa.Numeric(20, 8), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["grid_id"], ["grids.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["grid_orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trade_events_created_at"), "trade_events", ["created_at"], unique=False)
    op.create_index(op.f("ix_trade_events_grid_id"), "trade_events", ["grid_id"], unique=False)

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.String(100), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_log_action"), "audit_log", ["action"], unique=False)
    op.create_index(op.f("ix_audit_log_created_at"), "audit_log", ["created_at"], unique=False)
    op.create_index(op.f("ix_audit_log_user_id"), "audit_log", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_log_user_id"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_created_at"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_action"), table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index(op.f("ix_trade_events_grid_id"), table_name="trade_events")
    op.drop_index(op.f("ix_trade_events_created_at"), table_name="trade_events")
    op.drop_table("trade_events")

    op.drop_index(op.f("ix_grid_orders_status"), table_name="grid_orders")
    op.drop_index(op.f("ix_grid_orders_grid_id"), table_name="grid_orders")
    op.drop_index(op.f("ix_grid_orders_exchange_order_id"), table_name="grid_orders")
    op.drop_table("grid_orders")

    op.drop_index(op.f("ix_grids_account_id"), table_name="grids")
    op.drop_table("grids")

    op.drop_index(op.f("ix_exchange_accounts_owner_id"), table_name="exchange_accounts")
    op.drop_table("exchange_accounts")

    op.drop_index(op.f("ix_user_invites_token"), table_name="user_invites")
    op.drop_index(op.f("ix_user_invites_email"), table_name="user_invites")
    op.drop_table("user_invites")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS trade_event_type")
    op.execute("DROP TYPE IF EXISTS order_status")
    op.execute("DROP TYPE IF EXISTS order_side")
    op.execute("DROP TYPE IF EXISTS grid_status")
    op.execute("DROP TYPE IF EXISTS grid_mode")
    op.execute("DROP TYPE IF EXISTS user_role")
