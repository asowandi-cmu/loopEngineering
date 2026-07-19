"""Journal view — homepage HTML shell + RESTful JSON API.

Routes are intentionally thin: they validate the request with Pydantic schemas,
delegate to ``controllers/trade.py`` for all business logic, and translate the
result into the correct status code. Validation failures return HTTP 400 with a
``fields`` map (``{field: message}``) so the frontend can render inline errors;
missing rows return 404 JSON. Both stay consistent with ``errors.py``'s
content-negotiated shape but are emitted directly here so the ``fields`` map and
JSON content-type are deterministic regardless of the request's Accept header.
"""
from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, render_template, request
from pydantic import ValidationError

from ..controllers import trade as trade_controller
from ..schemas.trade import (
    StatsResponse,
    TradeCreate,
    TradeResponse,
    TradeUpdate,
)

journal_bp = Blueprint('journal', __name__)


def _serialize(trade: Any) -> dict[str, Any]:
    """Serialize a Trade ORM row to a JSON-ready dict."""
    return TradeResponse.model_validate(trade).model_dump(mode='json')


def _validation_error(exc: ValidationError) -> tuple[Any, int]:
    """Turn a Pydantic ValidationError into a 400 JSON body with a fields map."""
    fields: dict[str, str] = {}
    for err in exc.errors():
        loc = err['loc'][-1] if err['loc'] else '_'
        message = err['msg']
        # Strip Pydantic's "Value error, " prefix from custom validators.
        prefix = 'Value error, '
        if message.startswith(prefix):
            message = message[len(prefix):]
        fields[str(loc)] = message
    body = jsonify(
        error='Bad Request',
        message='Validation failed',
        fields=fields,
    )
    return body, 400


def _not_found() -> tuple[Any, int]:
    """Emit a JSON 404 for a missing trade."""
    return jsonify(error='Not Found', message='Trade not found'), 404


@journal_bp.route('/')
def index() -> str:
    """Render the Trading Journal homepage (hosts the ``journal`` island)."""
    return render_template('journal.html')


@journal_bp.route('/api/trades', methods=['GET'])
def list_trades() -> Any:
    """List all trades, newest first."""
    trades = trade_controller.list_trades()
    return jsonify(trades=[_serialize(t) for t in trades])


@journal_bp.route('/api/trades', methods=['POST'])
def create_trade() -> Any:
    """Create a trade from a validated body; returns 201 with the new trade."""
    try:
        data = TradeCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _validation_error(exc)
    trade = trade_controller.create_trade(data)
    return jsonify(_serialize(trade)), 201


@journal_bp.route('/api/trades/stats', methods=['GET'])
def trade_stats() -> Any:
    """Return summary statistics over all trades (all-zero when empty)."""
    stats = trade_controller.compute_stats()
    return jsonify(StatsResponse.model_validate(stats).model_dump(mode='json'))


@journal_bp.route('/api/trades/<int:trade_id>', methods=['GET'])
def get_trade(trade_id: int) -> Any:
    """Fetch one trade, or 404 if it does not exist."""
    trade = trade_controller.get_trade(trade_id)
    if trade is None:
        return _not_found()
    return jsonify(_serialize(trade))


@journal_bp.route('/api/trades/<int:trade_id>', methods=['PUT'])
def update_trade(trade_id: int) -> Any:
    """Full-replace update; recomputes derived columns. 404 if missing."""
    try:
        data = TradeUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return _validation_error(exc)
    trade = trade_controller.update_trade(trade_id, data)
    if trade is None:
        return _not_found()
    return jsonify(_serialize(trade))


@journal_bp.route('/api/trades/<int:trade_id>', methods=['DELETE'])
def delete_trade(trade_id: int) -> Any:
    """Delete a trade; 204 on success, 404 if missing."""
    if not trade_controller.delete_trade(trade_id):
        return _not_found()
    return '', 204
