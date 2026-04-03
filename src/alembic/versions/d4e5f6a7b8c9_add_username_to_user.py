"""add username and first_name to user

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-31 03:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("username", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "user",
        sa.Column("first_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user", "first_name")
    op.drop_column("user", "username")
