"""drop hello table

The Hello World tutorial scaffold has been replaced by the Space Invaders
game, which is entirely client-side and requires no database tables. This
migration drops the now-unused ``hello`` table.

We add a new migration (rather than deleting the create migration) so that
``script/setup`` remains reproducible for existing databases: applying the
full migration chain creates then drops the table, leaving a clean schema.

Revision ID: f1a2b3c4d5e6
Revises: e31396db40b1
Create Date: 2026-05-29 15:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'e31396db40b1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table('hello')


def downgrade() -> None:
    op.create_table(
        'hello',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
