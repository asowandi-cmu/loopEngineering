"""Trade-source adapter interface — the normalized ``Fill`` + ``TradeSource`` base.

Phase 2 supports several fill origins (a live DXtrade WebSocket, a CSV/statement
export, a test stub) behind **one** interface so they all feed the single
reconciliation pipeline. Each adapter's only job is to emit normalized ``Fill``s;
all aggregation/dedupe/P&L lives downstream in ``controllers/reconciliation.py``.

Two capabilities, either of which an adapter may implement:

- ``stream_fills()`` — async generator for live sources (the worker holds it open).
- ``fetch_fills(since)`` — batch pull for statement/backfill/replay sources.

``Fill`` is a plain frozen dataclass (no decorators for business logic, matching
Phase 1). Money/price fields are ``Decimal`` and timestamps carry whatever tz the
source provides — the pipeline normalizes to naive-UTC on persistence, so adapters
never have to.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


class TradeSourceError(Exception):
    """Raised when an adapter cannot authenticate, connect, or parse input."""


@dataclass(frozen=True)
class Fill:
    """A single normalized broker execution.

    ``external_exec_id`` is the broker's unique execution id and the idempotency
    key: the pipeline stores each fill exactly once by it, so replays/reconnects
    never double-count. ``action`` is ``'buy'`` or ``'sell'``; ``quantity`` is a
    positive contract count; ``price``/``fee`` are ``Decimal``.
    """

    external_exec_id: str
    symbol: str
    action: str  # 'buy' | 'sell'
    quantity: int
    price: Decimal
    executed_at: datetime
    fee: Decimal = Decimal('0')
    external_order_id: str | None = None
    account: str | None = None
    raw: str | None = None  # original payload (JSON) for audit
    tags: dict[str, Any] = field(default_factory=dict)  # adapter-specific extras


class TradeSource:
    """Base adapter. Concrete sources override the capabilities they support."""

    #: label written to ``broker_fills.source`` (``'dxtrade'`` | ``'csv'`` | ...).
    name: str = 'base'

    def fetch_fills(self, since: str | None = None) -> list[Fill]:
        """Return a batch of fills (optionally since a cursor). Override in batch
        sources; live-only sources may leave this raising."""
        raise NotImplementedError(
            f"{type(self).__name__} does not support fetch_fills()"
        )

    async def stream_fills(self) -> AsyncIterator[Fill]:
        """Yield fills as they arrive. Override in live sources; batch-only sources
        may leave this raising."""
        raise NotImplementedError(
            f"{type(self).__name__} does not support stream_fills()"
        )
        # Unreachable, but marks this as an async generator for type-checkers.
        yield  # pragma: no cover
