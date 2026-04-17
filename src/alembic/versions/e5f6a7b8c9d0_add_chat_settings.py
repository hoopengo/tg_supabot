"""add chat_settings table

Revision ID: e5f6a7b8c9d0
Revises: bdccd84b86e6
Create Date: 2025-04-17 12:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "bdccd84b86e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("cmd_dick", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "cmd_top_dick", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("cmd_stats", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("cmd_casino", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "cmd_casino_top", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("cmd_slots", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "cmd_sanitary", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("cmd_all", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "cmd_top_toxic", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "cmd_transfer", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("cmd_queues", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "cmd_create_queue", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("cmd_switch", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chat_id"),
    )
    op.create_index("ix_chat_settings_chat_id", "chat_settings", ["chat_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_settings_chat_id", table_name="chat_settings")
    op.drop_table("chat_settings")
