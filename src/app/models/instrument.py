"""Instrument model — the ``symbol → tick spec`` map Phase 1 anticipated.

Imported broker fills carry no tick specification, so the reconciliation
pipeline looks up ``symbol → (tick_size, tick_value, multiplier)`` here and
**snapshots** the result onto each ``trades`` row (Phase 1 already stores
per-trade ``tick_size``/``tick_value``). Editing an instrument therefore never
rewrites historical P&L — the same denormalization rationale as Phase 1.

A symbol with no row here is *not* guessed at: its trade is created
``needs_review`` with placeholder tick spec and no P&L until a spec is seeded
and ``reconcile_all()`` is re-run.

All price/value fields use ``Numeric``/``Decimal`` (never float); timestamps are
naive-UTC so SQLite (tests) and PostgreSQL (runtime) round-trip identically.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import db


def _utcnow() -> datetime:
    """Return the current UTC time as a naive datetime (see ``trade._utcnow``)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Instrument(db.Model):  # type: ignore[name-defined,misc]
    """Tick specification for a futures root symbol (e.g. ``ES``, ``MNQ``)."""

    __tablename__ = 'instruments'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tick_size: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    tick_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    multiplier: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return f"<Instrument {self.symbol} tick={self.tick_size}/{self.tick_value}>"
