"""add source and broker sync

Phase 2 (automated DXtrade fill sync). Extends the ``trades`` table with the
source/dedupe/review columns and adds three new tables:

- ``instruments``  — the ``symbol → tick spec`` map, snapshotted onto trades.
- ``broker_fills`` — the raw per-execution idempotency + cursor store.
- ``sync_state``   — the single-row worker/UI connection channel (id=1).

The ``trades`` columns are added with a ``server_default`` so existing Phase 1
rows backfill to ``source='manual'``/``review_status='ok'`` before the NOT NULL
takes effect; ``op.batch_alter_table`` is used because SQLite (the test DB)
cannot ``ALTER`` a column in place. ``external_id`` gets a unique index —
PostgreSQL and SQLite both allow many NULLs under it, so manual rows are
unaffected. Column types/scales mirror the models exactly (Numeric, never float;
naive-UTC DateTimes). ``downgrade()`` reverses in dependency order.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-21 12:00:00.000000

"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Extend trades ---------------------------------------------------
    # server_default backfills existing rows; the ORM supplies these values on
    # its own write path, matching the Phase 1 default convention.
    with op.batch_alter_table('trades', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'source', sa.String(length=16),
                nullable=False, server_default='manual',
            )
        )
        batch_op.add_column(
            sa.Column('external_id', sa.String(length=128), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                'review_status', sa.String(length=16),
                nullable=False, server_default='ok',
            )
        )
        batch_op.add_column(
            sa.Column('duplicate_of', sa.Integer(), nullable=True)
        )
        batch_op.create_unique_constraint('uq_trades_external_id', ['external_id'])
        batch_op.create_foreign_key(
            'fk_trades_duplicate_of', 'trades', ['duplicate_of'], ['id']
        )

    # --- instruments -----------------------------------------------------
    op.create_table(
        'instruments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=16), nullable=False),
        sa.Column('description', sa.String(length=120), nullable=True),
        sa.Column('tick_size', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('tick_value', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('multiplier', sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column('exchange', sa.String(length=16), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('symbol', name='uq_instruments_symbol'),
    )

    # --- broker_fills ----------------------------------------------------
    op.create_table(
        'broker_fills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('external_exec_id', sa.String(length=128), nullable=False),
        sa.Column('external_order_id', sa.String(length=128), nullable=True),
        sa.Column('account', sa.String(length=64), nullable=True),
        sa.Column('symbol', sa.String(length=16), nullable=False),
        sa.Column('action', sa.String(length=4), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('price', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column('fee', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('executed_at', sa.DateTime(), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.Column('raw', sa.Text(), nullable=True),
        sa.Column('ingested_at', sa.DateTime(), nullable=False),
        sa.Column('processed', sa.Boolean(), nullable=False),
        sa.Column('trade_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'external_exec_id', name='uq_broker_fills_external_exec_id'
        ),
        sa.ForeignKeyConstraint(
            ['trade_id'], ['trades.id'], name='fk_broker_fills_trade_id'
        ),
    )

    # --- sync_state (singleton row id=1) ---------------------------------
    sync_state = op.create_table(
        'sync_state',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('last_cursor', sa.String(length=128), nullable=True),
        sa.Column('last_fill_at', sa.DateTime(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.bulk_insert(
        sync_state,
        [{
            'id': 1,
            'enabled': False,
            'status': 'disconnected',
            'last_cursor': None,
            'last_fill_at': None,
            'last_synced_at': None,
            'last_error': None,
            'updated_at': datetime.now(timezone.utc).replace(tzinfo=None),
        }],
    )


def downgrade() -> None:
    op.drop_table('sync_state')
    op.drop_table('broker_fills')
    op.drop_table('instruments')
    with op.batch_alter_table('trades', schema=None) as batch_op:
        batch_op.drop_constraint('fk_trades_duplicate_of', type_='foreignkey')
        batch_op.drop_constraint('uq_trades_external_id', type_='unique')
        batch_op.drop_column('duplicate_of')
        batch_op.drop_column('review_status')
        batch_op.drop_column('external_id')
        batch_op.drop_column('source')
