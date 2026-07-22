"""Sync controller — the web/worker shared-state + credentials + CSV import glue.

Phase 2's web tier and background worker never share in-process state; they
coordinate **only through the database** (``sync_state``) and a gitignored secret
file (credentials). This module owns both channels so the view and worker stay
thin:

- ``get_sync_state`` returns the singleton ``sync_state`` row (id=1), creating it
  on first access so a freshly ``db.create_all()``-ed test DB (which skips the
  migration's seed INSERT) behaves identically to a migrated one.
- ``set_enabled`` writes the *desired* streaming state the UI toggles; the worker
  observes it and owns the socket. Status is written back by ``record_status``.
- Credentials follow spec Decision 5: the **environment is the source of truth**,
  with an optional write-through to a gitignored secret file so a single-user
  deployment can configure without shell access. ``load_credentials`` merges
  per-field (env wins), ``credentials_configured`` reports only *whether* a
  usable username+password resolves, and the password is **never** returned by an
  API nor logged.
- ``import_csv`` runs an uploaded statement through the same reconciliation
  pipeline as the live feed, tagging the raw fills' channel as ``'csv'`` (the
  resulting ``trades`` still carry ``source='dxtrade'`` — see reconciliation).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import current_app
from sqlalchemy import func, select

from ..models import BrokerFill, SyncState, Trade, db
from ..sources.csv_statement import CsvStatementSource
from ..sources.demo import DEMO_CREDENTIALS, demo_source
from .instrument import seed_default_instruments
from .reconciliation import ReconcileResult, ingest_fills

# (config attr, secret-file key) for each credential field; env wins per-field.
_CRED_FIELDS: tuple[tuple[str, str], ...] = (
    ('DXTRADE_USERNAME', 'username'),
    ('DXTRADE_PASSWORD', 'password'),
    ('DXTRADE_DOMAIN', 'domain'),
    ('DXTRADE_BASE_URL', 'base_url'),
    ('DXTRADE_WS_URL', 'ws_url'),
)


def _utcnow() -> datetime:
    """Current UTC time as a naive datetime (matches the model convention)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- Sync-state channel -------------------------------------------------------


def get_sync_state() -> SyncState:
    """Return the singleton ``sync_state`` row, creating it if absent."""
    state = db.session.get(SyncState, 1)
    if state is None:
        state = SyncState(id=1, enabled=False, status='disconnected')
        db.session.add(state)
        db.session.commit()
    return state


def set_enabled(enabled: bool) -> SyncState:
    """Set the *desired* streaming state; the worker reacts and owns status."""
    state = get_sync_state()
    state.enabled = enabled
    db.session.commit()
    return state


def record_status(
    status: str,
    *,
    error: str | None = None,
    cursor: str | None = None,
    fill_at: datetime | None = None,
) -> SyncState:
    """Worker → DB status write. Records ``last_synced_at`` while streaming."""
    state = get_sync_state()
    state.status = status
    state.last_error = error
    if cursor is not None:
        state.last_cursor = cursor
    if fill_at is not None:
        state.last_fill_at = fill_at
    if status == 'streaming':
        state.last_synced_at = _utcnow()
    db.session.commit()
    return state


def status_counts() -> dict[str, int]:
    """Headline counts for the status endpoint (imported trades / fills / review)."""
    trades_dxtrade = db.session.execute(
        select(func.count()).select_from(Trade).where(Trade.source == 'dxtrade')
    ).scalar_one()
    fills = db.session.execute(
        select(func.count()).select_from(BrokerFill)
    ).scalar_one()
    needs_review = db.session.execute(
        select(func.count()).select_from(Trade)
        .where(Trade.review_status == 'needs_review')
    ).scalar_one()
    return {
        'trades_dxtrade': int(trades_dxtrade),
        'fills': int(fills),
        'needs_review': int(needs_review),
    }


# --- Credentials channel (env source of truth + gitignored write-through) ------


def _secret_path() -> Path:
    return Path(current_app.config['DXTRADE_SECRET_FILE'])


def _read_secret_file() -> dict[str, Any]:
    path = _secret_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_credentials() -> dict[str, str | None]:
    """Resolve credentials per-field: environment wins, secret file fills gaps."""
    file_creds = _read_secret_file()
    resolved: dict[str, str | None] = {}
    for config_key, field in _CRED_FIELDS:
        env_value = current_app.config.get(config_key)
        resolved[field] = env_value or file_creds.get(field)
    return resolved


def credentials_configured() -> bool:
    """True when a usable username **and** password resolve (never the values)."""
    creds = load_credentials()
    return bool(creds.get('username') and creds.get('password'))


def save_credentials(
    *,
    username: str,
    password: str,
    domain: str,
    base_url: str | None = None,
    ws_url: str | None = None,
) -> None:
    """Write-through credentials to the gitignored secret file (mode 0600)."""
    path = _secret_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'username': username,
        'password': password,
        'domain': domain,
        'base_url': base_url,
        'ws_url': ws_url,
    }
    path.write_text(json.dumps(payload, indent=2))
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover - best-effort on platforms without chmod
        pass


# --- CSV import ---------------------------------------------------------------


def connect_test_account() -> ReconcileResult:
    """Activate the demo *test account* and auto-populate trades (no broker).

    Backs the connection panel's "Use test account" button: seeds the default
    tick specs (so the demo symbols resolve to real P&L), persists obviously-fake
    demo credentials so the status pill reads *configured*, marks the connection
    ``streaming``/``enabled``, then runs the canned demo fills through the *same*
    ``ingest_fills`` pipeline the live feed uses. Idempotent by the fills' stable
    ``DEMO-*`` ids: a repeat activation reports ``skipped_duplicates`` rather than
    creating duplicate trades.
    """
    seed_default_instruments()
    save_credentials(**DEMO_CREDENTIALS)
    result = ingest_fills(demo_source().fetch_fills(), source='dxtrade')
    set_enabled(True)
    record_status('streaming', cursor='demo', fill_at=_utcnow())
    return result


def import_csv(data: bytes) -> ReconcileResult:
    """Parse an uploaded statement CSV and run it through reconciliation.

    Raises ``TradeSourceError`` (translated to 400 by the view) on unparseable
    input. The raw fills are tagged channel ``'csv'``; resulting trades still
    carry ``source='dxtrade'`` like any imported trade.
    """
    source = CsvStatementSource.from_bytes(data)
    return ingest_fills(source.fetch_fills(), source='csv')
