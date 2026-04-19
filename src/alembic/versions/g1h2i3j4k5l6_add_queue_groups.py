"""add queue groups tables

Revision ID: g1h2i3j4k5l6
Revises: a1b2c3d4e5f7
Create Date: 2026-04-19 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "g1h2i3j4k5l6"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "queue_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_queue_groups_chat_id", "queue_groups", ["chat_id"])

    op.create_table(
        "queue_group_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("queue_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["group_id"], ["queue_groups.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["queue_id"], ["queues.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_queue_group_members_group_id", "queue_group_members", ["group_id"]
    )
    op.create_index(
        "ix_queue_group_members_queue_id", "queue_group_members", ["queue_id"]
    )
    op.create_index(
        "ix_queue_group_members_group_queue",
        "queue_group_members",
        ["group_id", "queue_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_queue_group_members_group_queue", table_name="queue_group_members"
    )
    op.drop_index(
        "ix_queue_group_members_queue_id", table_name="queue_group_members"
    )
    op.drop_index(
        "ix_queue_group_members_group_id", table_name="queue_group_members"
    )
    op.drop_table("queue_group_members")
    op.drop_index("ix_queue_groups_chat_id", table_name="queue_groups")
    op.drop_table("queue_groups")
