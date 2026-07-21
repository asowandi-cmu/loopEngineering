"""Instrument controller tests — spec lookup, seeding, normalization.

The tick spec is the input imported trades cannot supply themselves, so a wrong
or missing lookup silently corrupts P&L. These tests pin the hit/miss behaviour,
case-insensitive symbol normalization, and seeding idempotency.
"""
from decimal import Decimal

from flask import Flask

from app.controllers.instrument import (
    get_spec,
    list_instruments,
    seed_default_instruments,
    upsert_instrument,
)


def test_seed_is_idempotent(app: Flask) -> None:
    with app.app_context():
        first = seed_default_instruments()
        again = seed_default_instruments()
        assert first == again
        # Seeding twice must not create duplicate rows.
        assert len(list_instruments()) == first


def test_get_spec_hit_and_normalization(app: Flask) -> None:
    with app.app_context():
        seed_default_instruments()
        for symbol in ('ES', 'es', ' Es '):
            spec = get_spec(symbol)
            assert spec is not None
            assert spec.symbol == 'ES'
            assert spec.tick_size == Decimal('0.25')
            assert spec.tick_value == Decimal('12.50')


def test_get_spec_miss_returns_none(app: Flask) -> None:
    with app.app_context():
        seed_default_instruments()
        assert get_spec('NOPE') is None


def test_upsert_updates_in_place(app: Flask) -> None:
    with app.app_context():
        upsert_instrument(
            symbol='zz', tick_size=Decimal('0.5'), tick_value=Decimal('1.0'),
            description='temp',
        )
        upsert_instrument(
            symbol='ZZ', tick_size=Decimal('0.25'), tick_value=Decimal('2.0'),
            description='updated',
        )
        rows = [i for i in list_instruments() if i.symbol == 'ZZ']
        assert len(rows) == 1
        assert rows[0].tick_size == Decimal('0.25')
        assert rows[0].tick_value == Decimal('2.0')
        assert rows[0].description == 'updated'
