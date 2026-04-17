"""rename cmd_ai to cmd_ask in chat_settings

Revision ID: a1b2c3d4e5f7
Revises: f6a7b8c9d0e1
Create Date: 2026-04-17 18:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("chat_settings", "cmd_ai", new_column_name="cmd_ask")


def downgrade() -> None:
    op.alter_column("chat_settings", "cmd_ask", new_column_name="cmd_ai")
