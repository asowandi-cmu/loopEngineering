"""CSV statement source — parse a DXtrade/Futures Elite fills export into ``Fill``s.

This is the **compliant fallback** for when live session streaming is unavailable
or disallowed by the prop firm's ToS: the user exports their fills/statement CSV
and imports it, and it flows through the exact same reconciliation pipeline as the
live feed. Column mapping is deliberately tolerant (case-insensitive, several
common header aliases) because broker exports vary; a row missing the essentials
(exec id, symbol, side, quantity, price, time) makes the whole import fail with a
``TradeSourceError`` so the user gets a clear 400 rather than silently-dropped
trades.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .base import Fill, TradeSource, TradeSourceError

# header alias → canonical field. Compared case-insensitively after stripping.
_ALIASES: dict[str, str] = {
    'exec id': 'external_exec_id',
    'execution id': 'external_exec_id',
    'exec_id': 'external_exec_id',
    'fill id': 'external_exec_id',
    'trade id': 'external_exec_id',
    'order id': 'external_order_id',
    'order_id': 'external_order_id',
    'account': 'account',
    'account id': 'account',
    'symbol': 'symbol',
    'instrument': 'symbol',
    'contract': 'symbol',
    'side': 'action',
    'action': 'action',
    'b/s': 'action',
    'buy/sell': 'action',
    'qty': 'quantity',
    'quantity': 'quantity',
    'filled qty': 'quantity',
    'size': 'quantity',
    'price': 'price',
    'fill price': 'price',
    'avg price': 'price',
    'fee': 'fee',
    'fees': 'fee',
    'commission': 'fee',
    'time': 'executed_at',
    'exec time': 'executed_at',
    'execution time': 'executed_at',
    'timestamp': 'executed_at',
    'date/time': 'executed_at',
    'filled time': 'executed_at',
}

_BUY = {'buy', 'b', 'bought', 'long'}
_SELL = {'sell', 's', 'sold', 'short'}


def _canonical(header: str) -> str | None:
    return _ALIASES.get(header.strip().lower())


def _parse_action(value: str) -> str:
    v = value.strip().lower()
    if v in _BUY:
        return 'buy'
    if v in _SELL:
        return 'sell'
    raise TradeSourceError(f"unrecognized side/action: {value!r}")


def _parse_time(value: str) -> datetime:
    raw = value.strip().replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%m/%d/%Y %H:%M:%S'):
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
    raise TradeSourceError(f"unparseable timestamp: {value!r}")


def parse_fills(text: str) -> list[Fill]:
    """Parse CSV text into ``Fill``s, or raise ``TradeSourceError``."""
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise TradeSourceError('empty CSV')

    colmap: dict[int, str] = {}
    for idx, raw_header in enumerate(header):
        field = _canonical(raw_header)
        if field is not None:
            colmap[idx] = field

    required = {'external_exec_id', 'symbol', 'action', 'quantity', 'price',
                'executed_at'}
    missing = required - set(colmap.values())
    if missing:
        raise TradeSourceError(
            'CSV missing required columns: ' + ', '.join(sorted(missing))
        )

    fills: list[Fill] = []
    for lineno, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue  # skip blank lines
        values: dict[str, str] = {}
        for idx, field in colmap.items():
            if idx < len(row):
                values[field] = row[idx]
        try:
            fill = Fill(
                external_exec_id=values['external_exec_id'].strip(),
                symbol=values['symbol'].strip().upper(),
                action=_parse_action(values['action']),
                quantity=int(values['quantity'].strip()),
                price=Decimal(values['price'].strip()),
                executed_at=_parse_time(values['executed_at']),
                fee=Decimal(values['fee'].strip()) if values.get('fee', '').strip()
                else Decimal('0'),
                external_order_id=(values.get('external_order_id') or '').strip()
                or None,
                account=(values.get('account') or '').strip() or None,
                raw=None,
            )
        except (KeyError, ValueError, InvalidOperation) as exc:
            raise TradeSourceError(f"row {lineno}: {exc}") from exc
        if not fill.external_exec_id:
            raise TradeSourceError(f"row {lineno}: missing exec id")
        if fill.quantity <= 0:
            raise TradeSourceError(f"row {lineno}: quantity must be > 0")
        fills.append(fill)
    return fills


class CsvStatementSource(TradeSource):
    """Batch source over a parsed fills/statement CSV."""

    name = 'csv'

    def __init__(self, text: str):
        self._fills = parse_fills(text)

    @classmethod
    def from_bytes(cls, data: bytes) -> 'CsvStatementSource':
        """Build from raw uploaded bytes (utf-8, BOM-tolerant)."""
        return cls(data.decode('utf-8-sig'))

    def fetch_fills(self, since: str | None = None) -> list[Fill]:
        return list(self._fills)
