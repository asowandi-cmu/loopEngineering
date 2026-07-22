"""Sync view — the Phase 2 ``/api/sync/*`` + ``/api/instruments`` JSON surface.

Like ``journal.py`` these routes are intentionally thin: validate with Pydantic,
delegate to ``controllers/sync.py`` + the reconciliation pipeline, translate to a
status code. Two things are load-bearing here:

- **Credential secrecy** — ``POST /credentials`` returns 204 with no body; the
  password is never echoed, and ``GET /status`` exposes only
  ``credentials_configured``.
- **The guarded test-ingest route** (``POST /api/sync/_test/ingest``) is attached
  by ``attach_test_routes`` **only** when ``TESTING``/``DEBUG`` is set, so it is
  genuinely absent (404) in production. It runs the real ``ingest_fills`` on a
  posted fixture batch, letting E2E/integration tests drive the automated pipeline
  deterministically with no live broker.
"""
from __future__ import annotations

from typing import Any

from flask import Blueprint, Flask, jsonify, request
from pydantic import ValidationError

from ..controllers import instrument as instrument_controller
from ..controllers import reconciliation as reconciliation_controller
from ..controllers import sync as sync_controller
from ..schemas.sync import (
    CredentialsPayload,
    DemoConnectResponse,
    InstrumentResponse,
    ReconcileResultResponse,
    SyncStatusResponse,
)
from ..sources import fill_from_dict
from ..sources.base import TradeSourceError
from .journal import _validation_error

sync_bp = Blueprint('sync', __name__)


def _bad_request(message: str) -> tuple[Any, int]:
    """Emit a JSON 400 consistent with ``errors.py``'s shape."""
    return jsonify(error='Bad Request', message=message), 400


def _status_payload() -> dict[str, Any]:
    """Build the ``SyncStatusResponse`` body from state + counts + creds flag."""
    state = sync_controller.get_sync_state()
    response = SyncStatusResponse(
        enabled=state.enabled,
        status=state.status,
        credentials_configured=sync_controller.credentials_configured(),
        last_synced_at=state.last_synced_at,
        last_fill_at=state.last_fill_at,
        last_error=state.last_error,
        counts=sync_controller.status_counts(),  # type: ignore[arg-type]
    )
    return response.model_dump(mode='json')


def _result_payload(result: reconciliation_controller.ReconcileResult) -> Any:
    body = ReconcileResultResponse.model_validate(result.as_dict())
    return jsonify(body.model_dump(mode='json'))


@sync_bp.route('/api/sync/status', methods=['GET'])
def sync_status() -> Any:
    """Return the observed sync state + live counts (no secrets)."""
    return jsonify(_status_payload())


@sync_bp.route('/api/sync/connect', methods=['POST'])
def sync_connect() -> Any:
    """Set desired state ``enabled=true``; 400 if credentials aren't configured."""
    if not sync_controller.credentials_configured():
        return _bad_request('DXtrade credentials are not configured')
    sync_controller.set_enabled(True)
    return jsonify(_status_payload())


@sync_bp.route('/api/sync/disconnect', methods=['POST'])
def sync_disconnect() -> Any:
    """Set desired state ``enabled=false`` (worker performs the clean disconnect)."""
    sync_controller.set_enabled(False)
    return jsonify(_status_payload())


@sync_bp.route('/api/sync/credentials', methods=['POST'])
def sync_credentials() -> Any:
    """Persist write-only credentials to the gitignored secret file; 204."""
    try:
        payload = CredentialsPayload.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _validation_error(exc)
    sync_controller.save_credentials(
        username=payload.username,
        password=payload.password,
        domain=payload.domain,
        base_url=payload.base_url,
        ws_url=payload.ws_url,
    )
    return '', 204


@sync_bp.route('/api/sync/import', methods=['POST'])
def sync_import() -> Any:
    """Import an uploaded statement CSV through reconciliation; 400 if unparseable."""
    upload = request.files.get('file')
    if upload is None:
        return _bad_request("multipart form field 'file' is required")
    try:
        result = sync_controller.import_csv(upload.read())
    except TradeSourceError as exc:
        return _bad_request(str(exc))
    return _result_payload(result)


@sync_bp.route('/api/sync/demo', methods=['POST'])
def sync_demo() -> Any:
    """Activate the demo test account: auto-populate trades + mark streaming.

    Runs the canned demo fills through the real reconciliation pipeline (no live
    broker, no real credentials) and returns the fresh status alongside the
    dedupe-visible ingest counts. Idempotent on repeat activation.
    """
    result = sync_controller.connect_test_account()
    body = DemoConnectResponse(
        status=SyncStatusResponse.model_validate(_status_payload()),
        result=ReconcileResultResponse.model_validate(result.as_dict()),
    )
    return jsonify(body.model_dump(mode='json'))


@sync_bp.route('/api/sync/reconcile', methods=['POST'])
def sync_reconcile() -> Any:
    """Re-derive every trade from stored fills (backfill / after a spec fix)."""
    return _result_payload(reconciliation_controller.reconcile_all())


@sync_bp.route('/api/instruments', methods=['GET'])
def list_instruments() -> Any:
    """Return all seeded tick specs."""
    instruments = instrument_controller.list_instruments()
    return jsonify(instruments=[
        InstrumentResponse.model_validate(inst).model_dump(mode='json')
        for inst in instruments
    ])


def _test_ingest() -> Any:
    """Guarded: run the real pipeline on a posted fixture-fill batch."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, list):
        return _bad_request('expected a JSON list of fill objects')
    try:
        fills = [fill_from_dict(row) for row in payload]
    except (KeyError, ValueError, TypeError) as exc:
        return _bad_request(f'invalid fill payload: {exc}')
    result = reconciliation_controller.ingest_fills(fills, source='dxtrade')
    return _result_payload(result)


def attach_test_routes(app: Flask) -> None:
    """Register the guarded ``_test/ingest`` route (only in TESTING/DEBUG)."""
    app.add_url_rule(
        '/api/sync/_test/ingest',
        endpoint='sync_test_ingest',
        view_func=_test_ingest,
        methods=['POST'],
    )
