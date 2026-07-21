"""BrokerFill model — the raw per-execution idempotency + cursor store.

Every execution the broker reports is persisted here exactly once, keyed by its
``external_exec_id``. This is the correctness backbone of Phase 2:

- **Idempotency**: ingestion upserts by ``external_exec_id``, so a reconnect,
  replay, or worker restart that re-delivers a fill is a no-op — no double count.
- **Determinism**: reconciliation is a pure function of the stored fills, so it
  can be re-run after a bug fix or a newly-seeded tick spec and reproduce the
  same trades (stable ``external_id``).
- **Cursor / audit**: restarts resume from the last stored fill, and "why did
  this trade appear?" is answerable by inspecting the constituent fills.

``processed``/``trade_id`` link a fill to the closed round-trip it folded into.
Money/price use ``Numeric``; ``executed_at``/``ingested_at`` are naive-UTC.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import db


def _utcnow() -> datetime:
    """Return the current UTC time as a naive datetime (see ``trade._utcnow``)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class BrokerFill(db.Model):  # type: ignore[name-defined,misc]
    """A single broker execution (fill) — the atom reconciliation aggregates."""

    __tablename__ = 'broker_fills'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_exec_id: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True
    )
    external_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    account: Mapped[str | None] = mapped_column(String(64), nullable=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(4), nullable=False)  # buy | sell
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fee: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal('0')
    )
    executed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # dxtrade | csv
    raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    processed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    trade_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey('trades.id'), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<BrokerFill {self.external_exec_id} {self.symbol} "
            f"{self.action} x{self.quantity} @ {self.price}>"
        )
