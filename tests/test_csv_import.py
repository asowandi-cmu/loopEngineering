"""CSV statement adapter tests — the compliant fallback path.

The CSV import is the path that ships value even if live streaming is disallowed,
so its parsing must be tolerant of header variants yet fail loudly (not silently
drop trades) on malformed input. These tests cover parse → ``Fill`` and an
end-to-end import through the same reconciliation pipeline.
"""
from decimal import Decimal
from pathlib import Path

import pytest
from flask import Flask

from app.controllers.instrument import seed_default_instruments
from app.controllers.reconciliation import ingest_fills
from app.controllers.trade import list_trades
from app.sources import CsvStatementSource, parse_fills
from app.sources.base import TradeSourceError

STATEMENTS = Path(__file__).parent / 'fixtures' / 'statements'


def _csv(name: str) -> bytes:
    return (STATEMENTS / name).read_bytes()


def test_parse_well_formed_csv() -> None:
    source = CsvStatementSource.from_bytes(_csv('futures_elite_fills.csv'))
    fills = source.fetch_fills()
    assert len(fills) == 4
    first = fills[0]
    assert first.external_exec_id == 'C1'
    assert first.symbol == 'ES'
    assert first.action == 'buy'
    assert first.quantity == 1
    assert first.price == Decimal('5000.00')
    assert first.fee == Decimal('1.10')


def test_malformed_csv_raises() -> None:
    with pytest.raises(TradeSourceError):
        parse_fills('Foo,Bar,Baz\n1,2,3\n')


def test_empty_csv_raises() -> None:
    with pytest.raises(TradeSourceError):
        parse_fills('')


def test_end_to_end_import(app: Flask) -> None:
    with app.app_context():
        seed_default_instruments()
        source = CsvStatementSource.from_bytes(_csv('futures_elite_fills.csv'))
        result = ingest_fills(source.fetch_fills(), source='csv')
        assert result.created == 2  # ES long + NQ short round-trips
        trades = {t.symbol: t for t in list_trades()}
        assert trades['ES'].side == 'long'
        assert trades['ES'].net_pnl == Decimal('247.8000')  # 20t*12.50 - 2.20
        assert trades['NQ'].side == 'short'
        assert trades['NQ'].net_pnl == Decimal('197.8000')  # 40t*5 - 2.20
        # Imported trades carry source='dxtrade' regardless of ingest channel.
        assert all(t.source == 'dxtrade' for t in trades.values())
