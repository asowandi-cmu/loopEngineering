"""create trades table

Introduces the Trading Journal's single ``trades`` table (Phase 1: manual
completed-futures trades). Chains onto ``drop_hello_table`` so applying the full
migration chain against an existing database creates the hello table, drops it,
then creates ``trades`` — leaving exactly the Trading Journal schema.

Column types/nullability/scales mirror ``src/app/models/trade.py`` and the spec's
Data Model table. Money/price columns use ``Numeric`` (never float) for exact
financial math; ``ticks``/``gross_pnl``/``net_pnl`` are stored (denormalized),
written only by the controller's ``compute_pnl``.

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-07-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'trades',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=16), nullable=False),
        sa.Column('product_name', sa.String(length=120), nullable=True),
        sa.Column('side', sa.String(length=5), nullable=False),
        sa.Column('contracts', sa.Integer(), nullable=False),
        sa.Column('entry_price', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column('exit_price', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column('tick_size', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('tick_value', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('entry_at', sa.DateTime(), nullable=False),
        sa.Column('exit_at', sa.DateTime(), nullable=False),
        sa.Column('fees', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('ticks', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('gross_pnl', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('net_pnl', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('strategy', sa.String(length=80), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('trades')
