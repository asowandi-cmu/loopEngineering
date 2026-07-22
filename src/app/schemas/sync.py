"""Pydantic v2 schemas for the Phase 2 sync API.

These shape the ``/api/sync/*`` and ``/api/instruments`` surface. The design
rule that matters most here is **credential secrecy**: ``CredentialsPayload`` is
*write-only* (it validates an inbound payload but is never used to serialize a
response), and ``SyncStatusResponse`` deliberately exposes only *whether*
credentials are configured — never the username, and never the password. A
password must never leave the server via any response body (spec Decision 5).

Numeric instrument fields serialize as plain ``float`` for the JSON API (matching
``TradeResponse``'s convention); the ``Decimal`` values remain the source of truth
in the database.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class CredentialsPayload(BaseModel):
    """Write-only DXtrade credentials posted by the connection panel.

    Validated on the way in and handed to ``controllers/sync.save_credentials``;
    never serialized back out. ``base_url``/``ws_url`` are optional overrides for
    non-default DXtrade deployments.
    """

    model_config = ConfigDict(extra='ignore')

    username: str
    password: str
    domain: str
    base_url: str | None = None
    ws_url: str | None = None

    @field_validator('username', 'password', 'domain')
    @classmethod
    def _require_non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('must not be empty')
        return cleaned

    @field_validator('base_url', 'ws_url')
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class SyncCounts(BaseModel):
    """Live headline counts the UI shows next to the status pill."""

    trades_dxtrade: int
    fills: int
    needs_review: int


class SyncStatusResponse(BaseModel):
    """Observed sync state the UI polls — no secrets, only booleans + counts."""

    enabled: bool
    status: str
    credentials_configured: bool
    last_synced_at: datetime | None
    last_fill_at: datetime | None
    last_error: str | None
    counts: SyncCounts


class ReconcileResultResponse(BaseModel):
    """Dedupe-visible counts returned by import / reconcile / test-ingest."""

    created: int
    updated: int
    skipped_duplicates: int
    flagged: int
    open_positions: int


class DemoConnectResponse(BaseModel):
    """Returned by the test-account route: fresh status + the ingest result.

    The panel needs both in one round-trip — the ``status`` to refresh the pill
    (now *streaming*/configured) and the ``result`` to show the dedupe summary.
    """

    status: SyncStatusResponse
    result: ReconcileResultResponse


class InstrumentResponse(BaseModel):
    """A tick spec, for the instruments listing / future symbol editor."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    description: str | None
    tick_size: float
    tick_value: float
    multiplier: float | None
    exchange: str | None
