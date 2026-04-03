"""add first_name and username to chat_admins

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-31 02:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_admins",
        sa.Column("first_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "chat_admins",
        sa.Column("username", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_admins", "username")
    op.drop_column("chat_admins", "first_name")
