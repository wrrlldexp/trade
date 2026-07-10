"""Add ultraadmin role to user_role enum.

Revision ID: 20260517_0005
Revises: 20260517_0004
Create Date: 2026-05-17 14:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260517_0005"
down_revision: str | None = "20260517_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL: добавляем значение в существующий enum
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'ultraadmin' BEFORE 'superadmin'")


def downgrade() -> None:
    # PostgreSQL не позволяет удалять значения из enum
    pass
