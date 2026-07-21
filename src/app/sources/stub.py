"""Stub trade source — replays a fixed list of ``Fill``s with no network.

Used by tests, local dev, and the guarded ``/api/sync/_test/ingest`` endpoint to
drive the *real* reconciliation pipeline deterministically. It implements both
capabilities: ``fetch_fills`` returns the list, ``stream_fills`` yields it in
order. A helper (``from_dicts``) builds one straight from JSON fixtures.
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from datetime import datetime
from decimal import Decimal
from typing import Any

from .base import Fill, TradeSource


def fill_from_dict(data: dict[str, Any]) -> Fill:
    """Build a ``Fill`` from a plain dict (JSON fixture / API payload).

    Accepts ISO-8601 strings or ``datetime`` for ``executed_at`` and numeric or
    string prices/fees; everything is coerced to the ``Fill`` field types so the
    downstream pipeline sees a uniform shape.
    """
    executed_at = data['executed_at']
    if isinstance(executed_at, str):
        executed_at = datetime.fromisoformat(executed_at.replace('Z', '+00:00'))
    return Fill(
        external_exec_id=str(data['external_exec_id']),
        symbol=str(data['symbol']),
        action=str(data['action']).strip().lower(),
        quantity=int(data['quantity']),
        price=Decimal(str(data['price'])),
        executed_at=executed_at,
        fee=Decimal(str(data.get('fee', '0'))),
        external_order_id=(
            str(data['external_order_id'])
            if data.get('external_order_id') is not None else None
        ),
        account=(
            str(data['account']) if data.get('account') is not None else None
        ),
        raw=data.get('raw'),
    )


class StubTradeSource(TradeSource):
    """Replays a fixed list of fills (no network) for tests/dev/E2E."""

    name = 'dxtrade'

    def __init__(self, fills: Iterable[Fill]):
        self._fills = list(fills)

    @classmethod
    def from_dicts(cls, rows: Iterable[dict[str, Any]]) -> 'StubTradeSource':
        """Build a stub source from JSON-fixture dicts."""
        return cls(fill_from_dict(r) for r in rows)

    def fetch_fills(self, since: str | None = None) -> list[Fill]:
        return list(self._fills)

    async def stream_fills(self) -> AsyncIterator[Fill]:
        for fill in self._fills:
            yield fill
