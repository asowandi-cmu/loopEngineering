"""Trade model — a single completed futures trade.

Phase 1 records *closed* trades only, so exit fields are required. Each row
stores the raw inputs the trader entered (including the per-trade ``tick_size``
and ``tick_value``) **and** the derived values (``ticks``, ``gross_pnl``,
``net_pnl``). The derived columns are denormalized on purpose:

- the stats endpoint aggregates them directly in SQL (``SUM``/``COUNT``/``AVG``)
  with no per-row Python recomputation;
- each row is a stable historical snapshot — editing the tick spec of a *future*
  trade never silently rewrites past P&L;
- the frontend renders authoritative numbers without re-deriving them.

The only write path is ``controllers/trade.py``, which recomputes the derived
columns from the inputs on every create/update via the single ``compute_pnl``
source of truth — there is no API to set them directly.

All monetary/price fields use ``Numeric``/``Decimal`` (never ``float``) to avoid
binary-float rounding errors in financial math.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import db


def _utcnow() -> datetime:
    """Return the current UTC time as a naive datetime.

    Timestamps are stored naive-UTC so they round-trip identically across the
    PostgreSQL runtime DB and the SQLite test DB (neither column is tz-aware).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Trade(db.Model):  # type: ignore[name-defined,misc]
    """A completed futures trade with computed tick-based P&L."""

    __tablename__ = 'trades'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Raw inputs -----------------------------------------------------------
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    product_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    side: Mapped[str] = mapped_column(String(5), nullable=False)
    contracts: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    exit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    tick_size: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    tick_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    entry_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    exit_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fees: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal('0')
    )

    # Derived / stored (written by the controller, never by the client) ----
    ticks: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    gross_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    net_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    # Optional metadata ----------------------------------------------------
    strategy: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Source / dedupe (Phase 2) -------------------------------------------
    # ``source`` distinguishes a hand-entered trade from one auto-logged by the
    # broker-fill reconciliation pipeline; manual trades keep the Phase 1
    # behaviour exactly (``source='manual'``, ``external_id=NULL``). A deterministic
    # ``external_id`` per broker round-trip makes re-ingest/reconnect idempotent:
    # re-reconciling finds the existing row and updates-or-skips instead of
    # double-counting. ``review_status`` surfaces trades that need a human look
    # (unknown tick spec, or a likely overlap with a manual trade); ``duplicate_of``
    # points at the manual trade an import is suspected to duplicate — the import
    # is flagged, never silently merged or deleted.
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default='manual'
    )
    external_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True
    )
    review_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ok'
    )
    duplicate_of: Mapped[int | None] = mapped_column(
        Integer, ForeignKey('trades.id'), nullable=True
    )

    # Server-set audit timestamps -----------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<Trade id={self.id} {self.symbol} {self.side} "
            f"x{self.contracts} net={self.net_pnl}>"
        )
