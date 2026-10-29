"""add raffle tables

Revision ID: h1i2j3k4l5m6
Revises: g1h2i3j4k5l6
Create Date: 2026-10-29 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "h1i2j3k4l5m6"
down_revision = "g1h2i3j4k5l6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raffles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("topic_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum("active", "finished", "cancelled", name="rafflestatus"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_raffles_chat_id", "raffles", ["chat_id"])
    op.create_index("ix_raffles_ends_at", "raffles", ["ends_at"])

    op.create_table(
        "raffle_participants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("raffle_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column(
            "joined_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("topic_number", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["raffle_id"], ["raffles.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "raffle_id", "user_id", name="ix_raffle_participants_raffle_user"
        ),
    )
    op.create_index(
        "ix_raffle_participants_raffle_id", "raffle_participants", ["raffle_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_raffle_participants_raffle_id", table_name="raffle_participants"
    )
    op.drop_table("raffle_participants")
    op.drop_index("ix_raffles_ends_at", table_name="raffles")
    op.drop_index("ix_raffles_chat_id", table_name="raffles")
    op.drop_table("raffles")
    sa.Enum(name="rafflestatus").drop(op.get_bind())
