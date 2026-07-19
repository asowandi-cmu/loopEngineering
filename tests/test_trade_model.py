"""Persistence + stored-derived-column tests for the ``Trade`` model.

These verify the denormalization contract: after a controller write, the stored
``ticks``/``gross_pnl``/``net_pnl`` match ``compute_pnl`` and satisfy
``net_pnl == gross_pnl - fees``. They also confirm ``Numeric`` round-trips (under
SQLite values come back as ``Decimal``/float, so we assert with tolerance) and
that server-set timestamps are populated.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.controllers.trade import create_trade
from app.models import Trade, db
from app.schemas.trade import TradeCreate


def _make(**kwargs: Any) -> Trade:
    payload: dict[str, Any] = {
        'symbol': 'es',
        'product_name': 'E-mini S&P 500',
        'side': 'long',
        'contracts': 2,
        'entry_price': '5000.00',
        'exit_price': '5010.00',
        'tick_size': '0.25',
        'tick_value': '12.50',
        'entry_at': datetime(2026, 7, 19, 13, 30),
        'exit_at': datetime(2026, 7, 19, 14, 5),
        'fees': '4.50',
        'strategy': 'ORB',
        'notes': 'clean breakout',
    }
    payload.update(kwargs)
    return create_trade(TradeCreate.model_validate(payload))


def _close(actual: Any, expected: str) -> bool:
    return abs(Decimal(str(actual)) - Decimal(expected)) < Decimal('0.001')


def test_persists_and_reads_back(app: Any) -> None:
    trade = _make()
    assert trade.id is not None

    fetched = db.session.get(Trade, trade.id)
    assert fetched is not None
    assert fetched.symbol == 'ES'  # normalized/uppercased by the schema
    assert fetched.side == 'long'
    assert fetched.contracts == 2


def test_stored_derived_columns_match_formula(app: Any) -> None:
    trade = _make()
    assert _close(trade.ticks, '40')
    assert _close(trade.gross_pnl, '1000')
    assert _close(trade.net_pnl, '995.5')
    assert _close(trade.net_pnl, str(Decimal(str(trade.gross_pnl)) - Decimal(str(trade.fees))))


def test_short_equivalent_matches(app: Any) -> None:
    trade = _make(side='short', entry_price='5010.00', exit_price='5000.00')
    assert _close(trade.ticks, '40')
    assert _close(trade.gross_pnl, '1000')
    assert _close(trade.net_pnl, '995.5')


def test_server_sets_timestamps(app: Any) -> None:
    trade = _make()
    assert trade.created_at is not None
    assert trade.updated_at is not None


def test_optional_fields_may_be_null(app: Any) -> None:
    trade = _make(product_name=None, strategy=None, notes=None)
    assert trade.product_name is None
    assert trade.strategy is None
    assert trade.notes is None


def test_large_contract_count_precision(app: Any) -> None:
    trade = _make(contracts=1000, fees='0')
    assert _close(trade.gross_pnl, '500000')
    assert _close(trade.net_pnl, '500000')
