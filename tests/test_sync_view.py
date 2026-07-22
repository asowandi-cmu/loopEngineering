"""Sync API tests — the HTTP surface that makes Phase 2 drivable.

These pin the observable contract the frontend and the automated E2E depend on:
the status shape (no secrets, live counts), connect/disconnect toggling the
*desired* ``enabled`` state, credentials being **write-only** (the password is
never returned), CSV import + reconcile returning dedupe-visible counts, and the
guarded ``_test/ingest`` route driving the real pipeline (with dedupe holding on
replay) while being genuinely **absent in production**. The last property is the
security-relevant one: a test-only ingest endpoint must not exist in prod.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.config import ProductionConfig
from app.controllers.instrument import seed_default_instruments
from app.models import Trade

FIXTURES = Path(__file__).parent / 'fixtures'


def _fixture(name: str) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads(
        (FIXTURES / 'dxtrade' / f'{name}.json').read_text()
    )
    return data


def _statement(name: str) -> bytes:
    return (FIXTURES / 'statements' / name).read_bytes()


# --- Status -------------------------------------------------------------------


def test_status_shape_on_empty_db(client: FlaskClient[Any]) -> None:
    resp = client.get('/api/sync/status')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['enabled'] is False
    assert body['status'] == 'disconnected'
    assert body['credentials_configured'] is False
    assert body['last_error'] is None
    assert body['counts'] == {'trades_dxtrade': 0, 'fills': 0, 'needs_review': 0}


# --- Connect / disconnect -----------------------------------------------------


def test_connect_requires_credentials(client: FlaskClient[Any]) -> None:
    resp = client.post('/api/sync/connect')
    assert resp.status_code == 400
    assert client.get('/api/sync/status').get_json()['enabled'] is False


def test_credentials_then_connect_disconnect(app: Flask, client: FlaskClient[Any], tmp_path: Path) -> None:
    app.config['DXTRADE_SECRET_FILE'] = str(tmp_path / 'dxtrade.json')

    resp = client.post('/api/sync/credentials', json={
        'username': 'trader', 'password': 's3cret', 'domain': 'default',
    })
    assert resp.status_code == 204
    assert resp.data == b''  # never echoes the payload / password

    # Password is not retrievable via status; only the boolean flag is.
    status = client.get('/api/sync/status').get_json()
    assert status['credentials_configured'] is True
    assert 's3cret' not in resp.get_data(as_text=True)
    assert 'password' not in status

    assert client.post('/api/sync/connect').status_code == 200
    assert client.get('/api/sync/status').get_json()['enabled'] is True

    assert client.post('/api/sync/disconnect').status_code == 200
    assert client.get('/api/sync/status').get_json()['enabled'] is False


def test_credentials_validation_rejects_blank(app: Flask, client: FlaskClient[Any], tmp_path: Path) -> None:
    app.config['DXTRADE_SECRET_FILE'] = str(tmp_path / 'dxtrade.json')
    resp = client.post('/api/sync/credentials', json={
        'username': '  ', 'password': 'x', 'domain': 'd',
    })
    assert resp.status_code == 400
    assert 'username' in resp.get_json()['fields']


# --- CSV import + reconcile ---------------------------------------------------


def test_import_csv_returns_counts(app: Flask, client: FlaskClient[Any]) -> None:
    seed_default_instruments()
    data = {'file': (io.BytesIO(_statement('futures_elite_fills.csv')), 'fills.csv')}
    resp = client.post('/api/sync/import', data=data,
                       content_type='multipart/form-data')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['created'] == 2
    assert body['skipped_duplicates'] == 0
    # A row now carries the imported source in TradeResponse.
    trades = client.get('/api/trades').get_json()['trades']
    assert any(t['source'] == 'dxtrade' for t in trades)


def test_import_missing_file_is_400(client: FlaskClient[Any]) -> None:
    resp = client.post('/api/sync/import', data={},
                       content_type='multipart/form-data')
    assert resp.status_code == 400


def test_import_malformed_csv_is_400(app: Flask, client: FlaskClient[Any]) -> None:
    seed_default_instruments()
    data = {'file': (io.BytesIO(_statement('malformed.csv')), 'bad.csv')}
    resp = client.post('/api/sync/import', data=data,
                       content_type='multipart/form-data')
    assert resp.status_code == 400


def test_reconcile_after_spec_seed(app: Flask, client: FlaskClient[Any]) -> None:
    # Ingest an unknown symbol first (needs_review, no P&L), then seed + reconcile.
    resp = client.post('/api/sync/_test/ingest', json=_fixture('unknown_symbol'))
    assert resp.get_json()['created'] == 1
    seed_default_instruments()
    from app.controllers.instrument import upsert_instrument
    from decimal import Decimal
    upsert_instrument(symbol='XYZ', tick_size=Decimal('0.01'),
                      tick_value=Decimal('1.0'))
    resp = client.post('/api/sync/reconcile')
    assert resp.status_code == 200
    assert resp.get_json()['updated'] == 1


# --- Demo test account --------------------------------------------------------


def test_demo_account_populates_and_marks_streaming(
    app: Flask, client: FlaskClient[Any], tmp_path: Path
) -> None:
    app.config['DXTRADE_SECRET_FILE'] = str(tmp_path / 'dxtrade.json')

    resp = client.post('/api/sync/demo')
    assert resp.status_code == 200
    body = resp.get_json()

    # Three closed round-trips (ES/NQ/CL) + one still-open ES long.
    assert body['result']['created'] == 3
    assert body['result']['open_positions'] == 1
    assert body['result']['skipped_duplicates'] == 0

    # The connection now reads configured + streaming without real credentials.
    assert body['status']['credentials_configured'] is True
    assert body['status']['enabled'] is True
    assert body['status']['status'] == 'streaming'
    assert body['status']['counts']['trades_dxtrade'] == 3

    # The synced trades are real, P&L-bearing dxtrade rows.
    trades = client.get('/api/trades').get_json()['trades']
    dxtrade = [t for t in trades if t['source'] == 'dxtrade']
    assert len(dxtrade) == 3
    assert all(t['review_status'] == 'ok' for t in dxtrade)


def test_demo_account_is_idempotent_on_replay(
    app: Flask, client: FlaskClient[Any], tmp_path: Path
) -> None:
    app.config['DXTRADE_SECRET_FILE'] = str(tmp_path / 'dxtrade.json')

    client.post('/api/sync/demo')
    second = client.post('/api/sync/demo').get_json()

    # Re-activating the test account creates no new trades — dupes are skipped.
    assert second['result']['created'] == 0
    assert second['result']['skipped_duplicates'] > 0
    assert len(client.get('/api/trades').get_json()['trades']) == 3


def test_demo_account_absent_credentials_leak(
    app: Flask, client: FlaskClient[Any], tmp_path: Path
) -> None:
    app.config['DXTRADE_SECRET_FILE'] = str(tmp_path / 'dxtrade.json')
    resp = client.post('/api/sync/demo')
    # The demo password must never surface in the response, like real creds.
    assert 'demo-test-account' not in resp.get_data(as_text=True)
    assert 'password' not in resp.get_json()['status']


# --- Instruments --------------------------------------------------------------


def test_list_instruments(app: Flask, client: FlaskClient[Any]) -> None:
    seed_default_instruments()
    resp = client.get('/api/instruments')
    assert resp.status_code == 200
    instruments = resp.get_json()['instruments']
    symbols = {i['symbol'] for i in instruments}
    assert 'ES' in symbols
    es = next(i for i in instruments if i['symbol'] == 'ES')
    assert es['tick_size'] == 0.25 and es['tick_value'] == 12.5


# --- Guarded test-ingest route ------------------------------------------------


def test_test_ingest_runs_pipeline_and_dedupes(app: Flask, client: FlaskClient[Any]) -> None:
    seed_default_instruments()
    payload = _fixture('simple_round_trip')

    first = client.post('/api/sync/_test/ingest', json=payload)
    assert first.status_code == 200
    assert first.get_json()['created'] == 1

    trades = client.get('/api/trades').get_json()['trades']
    imported = [t for t in trades if t['source'] == 'dxtrade']
    assert len(imported) == 1
    assert imported[0]['review_status'] == 'ok'
    assert imported[0]['external_id'] is not None
    assert imported[0]['net_pnl'] == 995.5  # matches compute_pnl

    # Re-POST the same batch: dedupe holds, row count unchanged.
    second = client.post('/api/sync/_test/ingest', json=payload)
    assert second.get_json()['created'] == 0
    assert second.get_json()['skipped_duplicates'] == 1
    assert len(client.get('/api/trades').get_json()['trades']) == 1


def test_test_ingest_rejects_non_list(client: FlaskClient[Any]) -> None:
    resp = client.post('/api/sync/_test/ingest', json={'not': 'a list'})
    assert resp.status_code == 400


def test_test_ingest_absent_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import create_app

    monkeypatch.setattr(ProductionConfig, 'SQLALCHEMY_DATABASE_URI', 'sqlite://')
    prod = create_app('production')
    assert prod.config['DEBUG'] is False and prod.config['TESTING'] is False
    client = prod.test_client()
    resp = client.post('/api/sync/_test/ingest', json=[],
                       headers={'Accept': 'application/json'})
    assert resp.status_code == 404


def test_status_counts_reflect_ingest(app: Flask, client: FlaskClient[Any]) -> None:
    seed_default_instruments()
    client.post('/api/sync/_test/ingest', json=_fixture('simple_round_trip'))
    counts = client.get('/api/sync/status').get_json()['counts']
    assert counts['trades_dxtrade'] == 1
    assert counts['fills'] == 2
    assert counts['needs_review'] == 0


def test_needs_review_counted(app: Flask, client: FlaskClient[Any]) -> None:
    client.post('/api/sync/_test/ingest', json=_fixture('unknown_symbol'))
    counts = client.get('/api/sync/status').get_json()['counts']
    assert counts['needs_review'] == 1
    # No manual/dxtrade trades should be double-counted as review-free.
    assert Trade.query.count() == 1
