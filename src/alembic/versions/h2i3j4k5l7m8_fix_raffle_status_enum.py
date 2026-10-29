"""fix raffle status column to native enum

Revision ID: h2i3j4k5l7m8
Revises: h1i2j3k4l5m6
Create Date: 2026-10-29 13:00:00.000000

Fixes deployments where the previous revision already created
raffles.status as varchar instead of the rafflestatus enum type.
Idempotent: safe on fresh installs where the type already exists.

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "h2i3j4k5l7m8"
down_revision = "h1i2j3k4l5m6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE rafflestatus AS ENUM ('active', 'finished', 'cancelled');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        ALTER TABLE raffles
        ALTER COLUMN status TYPE rafflestatus
        USING status::rafflestatus
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE raffles
        ALTER COLUMN status TYPE varchar(32)
        USING status::varchar
        """
    )
    op.execute("DROP TYPE IF EXISTS rafflestatus")
