"""Reconciliation pipeline tests — the heart of Phase 2.

Two layers are covered: the **pure** ``aggregate_round_trips`` (every fill
topology from the fixtures — partial fills, scale-in/out, multiple round-trips,
position flip, unknown symbol) and the **impure** ``ingest_fills``/
``reconcile_all`` (idempotent dedupe, unknown-spec review then fill-in, manual
overlap flagging, open positions). Realized P&L is asserted against ``compute_pnl``
so the weighted-average aggregation is verified to reproduce true dollars.
"""
import json
from typing import Any
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.controllers.instrument import seed_default_instruments, upsert_instrument
from app.controllers.reconciliation import (
    aggregate_round_trips,
    ingest_fills,
    net_position,
    reconcile_all,
)
from app.controllers.trade import compute_pnl, create_trade, list_trades
from app.models import BrokerFill, Trade, db
from app.schemas.trade import TradeCreate
from app.sources import fill_from_dict
from app.sources.base import Fill
from flask import Flask

FIXTURES = Path(__file__).parent / 'fixtures' / 'dxtrade'


def fills(name: str) -> list[Fill]:
    rows = json.loads((FIXTURES / f'{name}.json').read_text())
    return [fill_from_dict(r) for r in rows]


def _by_side(round_trips: list[Any]) -> list[Any]:
    return sorted(round_trips, key=lambda rt: (rt.entry_at, rt.side))


# --- Pure aggregation ---------------------------------------------------------


def test_simple_round_trip() -> None:
    (rt,) = aggregate_round_trips(fills('simple_round_trip'))
    assert rt.side == 'long'
    assert rt.contracts == 2
    assert rt.entry_price == Decimal('5000')
    assert rt.exit_price == Decimal('5010')
    assert rt.fees == Decimal('4.50')
    assert rt.exec_ids == ['E1', 'E2']
    assert rt.external_id.startswith('dxt:')


def test_partial_fills_weighted_average() -> None:
    (rt,) = aggregate_round_trips(fills('partial_fills'))
    assert rt.contracts == 2
    assert rt.entry_price == Decimal('18001')  # (18000 + 18002) / 2
    assert rt.exit_price == Decimal('18011')   # (18010 + 18012) / 2


def test_scale_in_out_weighted_average() -> None:
    (rt,) = aggregate_round_trips(fills('scale_in_out'))
    assert rt.contracts == 4
    assert rt.entry_price == Decimal('5003')  # (5000*1 + 5004*3) / 4
    assert rt.exit_price == Decimal('5009')   # (5010*2 + 5008*2) / 4
    assert rt.fees == Decimal('4.00')


def test_multiple_round_trips_split() -> None:
    rts = _by_side(aggregate_round_trips(fills('multiple_round_trips')))
    assert len(rts) == 2
    first, second = rts
    assert first.side == 'long' and first.entry_price == Decimal('75.00')
    assert second.side == 'short' and second.entry_price == Decimal('75.20')
    assert first.external_id != second.external_id


def test_position_flip_splits_crossing_fill() -> None:
    rts = _by_side(aggregate_round_trips(fills('position_flip')))
    assert len(rts) == 2
    long_rt, short_rt = rts
    assert long_rt.side == 'long' and long_rt.contracts == 2
    assert short_rt.side == 'short' and short_rt.contracts == 1
    # The crossing fill F2 belongs to BOTH round-trips.
    assert 'F2' in long_rt.exec_ids
    assert 'F2' in short_rt.exec_ids
    # Fees split proportionally by quantity consumed in each leg.
    assert long_rt.fees == Decimal('4.00')   # F1 2.00 + F2*(2/3) 2.00
    assert short_rt.fees == Decimal('2.00')  # F2*(1/3) 1.00 + F3 1.00


def test_open_position_emits_nothing() -> None:
    only_entry = fills('simple_round_trip')[:1]
    assert aggregate_round_trips(only_entry) == []
    assert net_position(only_entry) != 0


def test_external_id_is_stable_and_order_independent() -> None:
    a = aggregate_round_trips(fills('simple_round_trip'))[0]
    b = aggregate_round_trips(list(reversed(fills('simple_round_trip'))))[0]
    assert a.external_id == b.external_id


# --- Ingest / dedupe (DB) -----------------------------------------------------


def test_ingest_creates_one_trade_with_correct_pnl(app: Flask) -> None:
    with app.app_context():
        seed_default_instruments()
        result = ingest_fills(fills('simple_round_trip'))
        assert result.created == 1
        (trade,) = list_trades()
        assert trade.source == 'dxtrade'
        assert trade.external_id is not None
        assert trade.review_status == 'ok'
        ticks, gross, net = compute_pnl(
            side='long', contracts=2,
            entry_price=Decimal('5000'), exit_price=Decimal('5010'),
            tick_size=Decimal('0.25'), tick_value=Decimal('12.50'),
            fees=Decimal('4.50'),
        )
        assert trade.net_pnl == net == Decimal('995.5000')


def test_reingest_is_idempotent(app: Flask) -> None:
    with app.app_context():
        seed_default_instruments()
        ingest_fills(fills('simple_round_trip'))
        result = ingest_fills(fills('simple_round_trip'))
        assert result.created == 0
        assert result.skipped_duplicates == 1
        assert len(list_trades()) == 1
        # Raw fills stored exactly once, too.
        assert db.session.query(BrokerFill).count() == 2


def test_position_flip_creates_two_trades(app: Flask) -> None:
    with app.app_context():
        seed_default_instruments()
        result = ingest_fills(fills('position_flip'))
        assert result.created == 2
        trades = list_trades()
        sides = {t.side for t in trades}
        assert sides == {'long', 'short'}


def test_unknown_symbol_needs_review_then_filled_in(app: Flask) -> None:
    with app.app_context():
        seed_default_instruments()
        result = ingest_fills(fills('unknown_symbol'))
        assert result.created == 1
        (trade,) = list_trades()
        assert trade.review_status == 'needs_review'
        assert trade.net_pnl == Decimal('0')
        external_id = trade.external_id

        # Seed the missing spec and re-reconcile: same row, P&L filled in.
        upsert_instrument(
            symbol='XYZ', tick_size=Decimal('0.01'), tick_value=Decimal('1.0'),
        )
        result2 = reconcile_all()
        assert result2.updated == 1
        (trade,) = list_trades()
        assert trade.external_id == external_id
        assert trade.review_status == 'ok'
        assert trade.net_pnl == Decimal('99.0000')  # (101-100)/0.01=100t*1*1 -1 fee


def test_open_only_position_reports_open_no_trade(app: Flask) -> None:
    with app.app_context():
        seed_default_instruments()
        entry_only = fills('simple_round_trip')[:1]
        result = ingest_fills(entry_only)
        assert result.created == 0
        assert result.open_positions == 1
        assert list_trades() == []

        # Late closing fill completes the earlier-opened round-trip.
        closing = fills('simple_round_trip')[1:]
        result2 = ingest_fills(closing)
        assert result2.created == 1
        assert result2.open_positions == 0
        assert len(list_trades()) == 1


def test_import_flags_manual_overlap(app: Flask) -> None:
    with app.app_context():
        seed_default_instruments()
        manual = create_trade(TradeCreate.model_validate({
            'symbol': 'ES', 'side': 'long', 'contracts': 2,
            'entry_price': '5000.00', 'exit_price': '5010.00',
            'tick_size': '0.25', 'tick_value': '12.50',
            'entry_at': datetime(2026, 7, 20, 13, 30),
            'exit_at': datetime(2026, 7, 20, 13, 45),
            'fees': '4.50',
        }))
        result = ingest_fills(fills('simple_round_trip'))
        assert result.created == 1
        assert result.flagged == 1
        imported = [t for t in list_trades() if t.source == 'dxtrade']
        assert len(imported) == 1
        assert imported[0].review_status == 'needs_review'
        assert imported[0].duplicate_of == manual.id
        # Neither row deleted.
        assert db.session.query(Trade).count() == 2
