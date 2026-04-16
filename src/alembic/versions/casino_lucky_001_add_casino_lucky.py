"""add casino_lucky to user

Revision ID: casino_lucky_001
Revises: 920217c0495c
Create Date: 2026-04-17 00:45:00

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "casino_lucky_001"
down_revision = "920217c0495c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("casino_lucky", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("user", "casino_lucky")
