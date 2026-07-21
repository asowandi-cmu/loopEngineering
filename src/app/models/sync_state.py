"""SyncState model — the single-row connection/cursor/status record.

Phase 2's web tier and background worker share no in-process state; they
communicate **only through the database**. This one row (id=1) is that channel:

- ``enabled`` is the *desired* streaming state the UI toggles via
  connect/disconnect; the worker observes it and owns the socket.
- ``status`` is the *observed* state the worker reports back for the UI to poll
  (``disconnected`` | ``connecting`` | ``streaming`` | ``error``).
- ``last_cursor``/``last_fill_at``/``last_synced_at`` support durable resume, and
  ``last_error`` surfaces the most recent failure for display.

Timestamps are naive-UTC to match the rest of the schema.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import db


def _utcnow() -> datetime:
    """Return the current UTC time as a naive datetime (see ``trade._utcnow``)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SyncState(db.Model):  # type: ignore[name-defined,misc]
    """Singleton (id=1) desired-state + observed-status + cursor record."""

    __tablename__ = 'sync_state'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='disconnected'
    )
    last_cursor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_fill_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return f"<SyncState enabled={self.enabled} status={self.status!r}>"
