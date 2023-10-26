"""add toxic_level in user

Revision ID: 4dc3cbe276e2
Revises: f50b6ad6c736
Create Date: 2023-10-26 19:16:23.048810

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4dc3cbe276e2'
down_revision = 'f50b6ad6c736'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user', sa.Column('toxicity_level', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_user_penis_size'), 'user', ['penis_size'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_user_penis_size'), table_name='user')
    op.drop_column('user', 'toxicity_level')
    # ### end Alembic commands ###