"""add queue tables

Revision ID: a1b2c3d4e5f6
Revises: 920217c0495c
Create Date: 2026-03-30 23:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "920217c0495c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "queues",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "closed", name="queuestatus"),
            nullable=False,
            server_default="open",
        ),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_queues_chat_id", "queues", ["chat_id"])

    op.create_table(
        "queue_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("queue_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "joined_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "status",
            sa.Enum("active", "removed", name="memberstatus"),
            nullable=False,
            server_default="active",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["queue_id"], ["queues.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_queue_members_queue_position", "queue_members", ["queue_id", "position"]
    )
    op.create_index(
        "ix_queue_members_queue_user", "queue_members", ["queue_id", "user_id"]
    )

    op.create_table(
        "swap_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("queue_id", sa.Integer(), nullable=False),
        sa.Column("from_user_id", sa.BigInteger(), nullable=False),
        sa.Column("to_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", "expired", name="swapstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["queue_id"], ["queues.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_swap_requests_queue_id", "swap_requests", ["queue_id"])

    op.create_table(
        "chat_admins",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("super_admin", "admin", name="adminrole"),
            nullable=False,
            server_default="admin",
        ),
        sa.Column("added_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_admins_chat_id", "chat_admins", ["chat_id"])
    op.create_index("ix_chat_admins_chat_user", "chat_admins", ["chat_id", "user_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("queue_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_chat_id", "audit_log", ["chat_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_chat_id", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_chat_admins_chat_user", table_name="chat_admins")
    op.drop_index("ix_chat_admins_chat_id", table_name="chat_admins")
    op.drop_table("chat_admins")
    op.drop_index("ix_swap_requests_queue_id", table_name="swap_requests")
    op.drop_table("swap_requests")
    op.drop_index("ix_queue_members_queue_user", table_name="queue_members")
    op.drop_index("ix_queue_members_queue_position", table_name="queue_members")
    op.drop_table("queue_members")
    op.drop_index("ix_queues_chat_id", table_name="queues")
    op.drop_table("queues")

    sa.Enum(name="queuestatus").drop(op.get_bind())
    sa.Enum(name="memberstatus").drop(op.get_bind())
    sa.Enum(name="swapstatus").drop(op.get_bind())
    sa.Enum(name="adminrole").drop(op.get_bind())
