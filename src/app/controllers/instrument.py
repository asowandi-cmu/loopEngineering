"""Instrument controller — tick-spec lookup, upsert, and seeding.

Imported fills carry no tick spec, so reconciliation resolves ``symbol → (tick_size,
tick_value, multiplier)`` here and snapshots it onto each trade. Symbols are
normalized to an uppercased root so ``es``, ``ES``, and a dated contract root all
resolve to the same instrument. Plain functions, no decorators (Phase 1 style).
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from ..models import Instrument, db


def normalize_symbol(symbol: str) -> str:
    """Uppercase + strip a symbol to its lookup key."""
    return symbol.strip().upper()


def get_spec(symbol: str) -> Instrument | None:
    """Return the ``Instrument`` for ``symbol`` (normalized), or ``None``."""
    stmt = select(Instrument).where(Instrument.symbol == normalize_symbol(symbol))
    return db.session.execute(stmt).scalar_one_or_none()


def list_instruments() -> list[Instrument]:
    """Return all instruments ordered by symbol."""
    stmt = select(Instrument).order_by(Instrument.symbol.asc())
    return list(db.session.execute(stmt).scalars().all())


def upsert_instrument(
    *,
    symbol: str,
    tick_size: Decimal,
    tick_value: Decimal,
    description: str | None = None,
    multiplier: Decimal | None = None,
    exchange: str | None = None,
) -> Instrument:
    """Create or update an instrument by (normalized) symbol and persist it."""
    key = normalize_symbol(symbol)
    inst = get_spec(key)
    if inst is None:
        inst = Instrument(symbol=key)
        db.session.add(inst)
    inst.tick_size = tick_size
    inst.tick_value = tick_value
    inst.description = description
    inst.multiplier = multiplier
    inst.exchange = exchange
    db.session.commit()
    return inst


# Common CME/CBOT/NYMEX/COMEX futures the app seeds by default. tick_value is
# USD per tick per contract; multiplier is informational (dollars/point).
_DEFAULTS: list[dict[str, str]] = [
    {'symbol': 'ES', 'description': 'E-mini S&P 500', 'tick_size': '0.25',
     'tick_value': '12.50', 'multiplier': '50', 'exchange': 'CME'},
    {'symbol': 'MES', 'description': 'Micro E-mini S&P 500', 'tick_size': '0.25',
     'tick_value': '1.25', 'multiplier': '5', 'exchange': 'CME'},
    {'symbol': 'NQ', 'description': 'E-mini Nasdaq-100', 'tick_size': '0.25',
     'tick_value': '5.00', 'multiplier': '20', 'exchange': 'CME'},
    {'symbol': 'MNQ', 'description': 'Micro E-mini Nasdaq-100', 'tick_size': '0.25',
     'tick_value': '0.50', 'multiplier': '2', 'exchange': 'CME'},
    {'symbol': 'RTY', 'description': 'E-mini Russell 2000', 'tick_size': '0.10',
     'tick_value': '5.00', 'multiplier': '50', 'exchange': 'CME'},
    {'symbol': 'M2K', 'description': 'Micro E-mini Russell 2000',
     'tick_size': '0.10', 'tick_value': '0.50', 'multiplier': '5',
     'exchange': 'CME'},
    {'symbol': 'YM', 'description': 'E-mini Dow', 'tick_size': '1.0',
     'tick_value': '5.00', 'multiplier': '5', 'exchange': 'CBOT'},
    {'symbol': 'MYM', 'description': 'Micro E-mini Dow', 'tick_size': '1.0',
     'tick_value': '0.50', 'multiplier': '0.5', 'exchange': 'CBOT'},
    {'symbol': 'CL', 'description': 'Crude Oil', 'tick_size': '0.01',
     'tick_value': '10.00', 'multiplier': '1000', 'exchange': 'NYMEX'},
    {'symbol': 'MCL', 'description': 'Micro Crude Oil', 'tick_size': '0.01',
     'tick_value': '1.00', 'multiplier': '100', 'exchange': 'NYMEX'},
    {'symbol': 'GC', 'description': 'Gold', 'tick_size': '0.10',
     'tick_value': '10.00', 'multiplier': '100', 'exchange': 'COMEX'},
    {'symbol': 'MGC', 'description': 'Micro Gold', 'tick_size': '0.10',
     'tick_value': '1.00', 'multiplier': '10', 'exchange': 'COMEX'},
    {'symbol': 'SI', 'description': 'Silver', 'tick_size': '0.005',
     'tick_value': '25.00', 'multiplier': '5000', 'exchange': 'COMEX'},
    {'symbol': '6E', 'description': 'Euro FX', 'tick_size': '0.00005',
     'tick_value': '6.25', 'multiplier': '125000', 'exchange': 'CME'},
    {'symbol': '6J', 'description': 'Japanese Yen', 'tick_size': '0.0000005',
     'tick_value': '6.25', 'multiplier': '12500000', 'exchange': 'CME'},
    {'symbol': 'ZB', 'description': '30-Year U.S. Treasury Bond',
     'tick_size': '0.03125', 'tick_value': '31.25', 'multiplier': '1000',
     'exchange': 'CBOT'},
    {'symbol': 'ZN', 'description': '10-Year U.S. Treasury Note',
     'tick_size': '0.015625', 'tick_value': '15.625', 'multiplier': '1000',
     'exchange': 'CBOT'},
]


def seed_default_instruments() -> int:
    """Idempotently upsert the built-in instrument specs. Returns the count."""
    for spec in _DEFAULTS:
        upsert_instrument(
            symbol=spec['symbol'],
            description=spec['description'],
            tick_size=Decimal(spec['tick_size']),
            tick_value=Decimal(spec['tick_value']),
            multiplier=Decimal(spec['multiplier']),
            exchange=spec['exchange'],
        )
    return len(_DEFAULTS)
