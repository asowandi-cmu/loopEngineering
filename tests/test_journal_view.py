"""Tests for the Trading Journal view: homepage shell + JSON API + errors.

Covers the observable HTTP contract end-to-end: the homepage renders the island
mount, the CRUD lifecycle persists and recomputes correctly, the stats endpoint
aggregates (and returns all-zeros on an empty journal without dividing by zero),
and every invalid input the spec enumerates is rejected with a 400 ``fields``
map. The ``TestErrorHandlers`` cases are preserved from the removed game test so
content-negotiated error coverage survives the Space Invaders removal.
"""
from __future__ import annotations

import json
from typing import Any

from flask.testing import FlaskClient


def _valid_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'symbol': 'ES',
        'product_name': 'E-mini S&P 500',
        'side': 'long',
        'contracts': 2,
        'entry_price': 5000.00,
        'exit_price': 5010.00,
        'tick_size': 0.25,
        'tick_value': 12.50,
        'entry_at': '2026-07-19T13:30:00Z',
        'exit_at': '2026-07-19T14:05:00Z',
        'fees': 4.50,
        'strategy': 'ORB',
        'notes': 'clean breakout',
    }
    payload.update(overrides)
    return payload


def _post(client: FlaskClient[Any], **overrides: Any) -> Any:
    return client.post('/api/trades', json=_valid_payload(**overrides))


class TestJournalPage:
    """The homepage HTML shell that hosts the journal island."""

    def test_index_returns_html(self, client: FlaskClient[Any]) -> None:
        response = client.get('/')
        assert response.status_code == 200
        assert b'Trading Journal' in response.data

    def test_index_title(self, client: FlaskClient[Any]) -> None:
        response = client.get('/')
        assert b'<title>Trading Journal</title>' in response.data

    def test_index_contains_island_mount(self, client: FlaskClient[Any]) -> None:
        response = client.get('/')
        assert b'data-island="journal"' in response.data

    def test_no_space_invaders_anywhere(self, client: FlaskClient[Any]) -> None:
        response = client.get('/')
        assert b'Space Invaders' not in response.data


class TestTradeCrud:
    """Full create/read/update/delete lifecycle over the JSON API."""

    def test_create_returns_201_with_computed_pnl(self, client: FlaskClient[Any]) -> None:
        response = _post(client)
        assert response.status_code == 201
        body = response.get_json()
        assert body['id'] is not None
        assert body['symbol'] == 'ES'
        assert abs(body['ticks'] - 40) < 0.001
        assert abs(body['gross_pnl'] - 1000) < 0.001
        assert abs(body['net_pnl'] - 995.5) < 0.001

    def test_short_equivalent_matches(self, client: FlaskClient[Any]) -> None:
        response = _post(client, side='short', entry_price=5010.0, exit_price=5000.0)
        body = response.get_json()
        assert abs(body['ticks'] - 40) < 0.001
        assert abs(body['net_pnl'] - 995.5) < 0.001

    def test_list_newest_first(self, client: FlaskClient[Any]) -> None:
        _post(client, entry_at='2026-07-18T13:30:00Z', exit_at='2026-07-18T14:00:00Z')
        _post(client, entry_at='2026-07-20T13:30:00Z', exit_at='2026-07-20T14:00:00Z')
        response = client.get('/api/trades')
        assert response.status_code == 200
        trades = response.get_json()['trades']
        assert len(trades) == 2
        assert trades[0]['entry_at'] > trades[1]['entry_at']

    def test_get_one(self, client: FlaskClient[Any]) -> None:
        trade_id = _post(client).get_json()['id']
        response = client.get(f'/api/trades/{trade_id}')
        assert response.status_code == 200
        assert response.get_json()['id'] == trade_id

    def test_get_missing_returns_404(self, client: FlaskClient[Any]) -> None:
        response = client.get('/api/trades/99999')
        assert response.status_code == 404
        assert 'error' in response.get_json()

    def test_put_recomputes_derived_columns(self, client: FlaskClient[Any]) -> None:
        trade_id = _post(client).get_json()['id']
        response = client.put(
            f'/api/trades/{trade_id}',
            json=_valid_payload(exit_price=5020.0, contracts=1, fees=0),
        )
        assert response.status_code == 200
        body = response.get_json()
        assert abs(body['ticks'] - 80) < 0.001
        assert abs(body['gross_pnl'] - 1000) < 0.001
        assert abs(body['net_pnl'] - 1000) < 0.001

    def test_put_missing_returns_404(self, client: FlaskClient[Any]) -> None:
        response = client.put('/api/trades/99999', json=_valid_payload())
        assert response.status_code == 404

    def test_delete_then_404(self, client: FlaskClient[Any]) -> None:
        trade_id = _post(client).get_json()['id']
        response = client.delete(f'/api/trades/{trade_id}')
        assert response.status_code == 204
        assert client.get(f'/api/trades/{trade_id}').status_code == 404

    def test_delete_missing_returns_404(self, client: FlaskClient[Any]) -> None:
        assert client.delete('/api/trades/99999').status_code == 404

    def test_derived_fields_from_client_are_ignored(self, client: FlaskClient[Any]) -> None:
        response = _post(client, ticks=9999, gross_pnl=9999, net_pnl=9999)
        body = response.get_json()
        assert abs(body['ticks'] - 40) < 0.001
        assert abs(body['net_pnl'] - 995.5) < 0.001


class TestStats:
    """The summary-statistics aggregation endpoint."""

    def test_empty_journal_all_zeros(self, client: FlaskClient[Any]) -> None:
        body = client.get('/api/trades/stats').get_json()
        assert body['num_trades'] == 0
        assert body['total_net_pnl'] == 0
        assert body['win_rate'] == 0
        assert body['average_win'] == 0
        assert body['average_loss'] == 0

    def test_populated_stats(self, client: FlaskClient[Any]) -> None:
        # Winner: net 995.5
        _post(client)
        # Loser: long 5010 -> 5000, 1 contract, 0 fees => net -500
        _post(client, entry_price=5010.0, exit_price=5000.0, contracts=1, fees=0)
        # Scratch: entry == exit => net 0
        _post(client, entry_price=5000.0, exit_price=5000.0, contracts=1, fees=0)

        body = client.get('/api/trades/stats').get_json()
        assert body['num_trades'] == 3
        assert body['wins'] == 1
        assert body['losses'] == 1
        assert body['scratches'] == 1
        assert abs(body['win_rate'] - (1 / 3)) < 0.001
        assert abs(body['average_win'] - 995.5) < 0.001
        assert abs(body['average_loss'] - (-500)) < 0.001
        assert abs(body['total_net_pnl'] - 495.5) < 0.001


class TestValidation:
    """Every invalid input the spec enumerates must yield a 400 fields map."""

    def _assert_400_field(self, response: Any, field: str) -> None:
        assert response.status_code == 400
        body = response.get_json()
        assert body['error'] == 'Bad Request'
        assert field in body['fields']

    def test_zero_tick_size(self, client: FlaskClient[Any]) -> None:
        self._assert_400_field(_post(client, tick_size=0), 'tick_size')

    def test_negative_tick_size(self, client: FlaskClient[Any]) -> None:
        self._assert_400_field(_post(client, tick_size=-0.25), 'tick_size')

    def test_zero_tick_value(self, client: FlaskClient[Any]) -> None:
        self._assert_400_field(_post(client, tick_value=0), 'tick_value')

    def test_contracts_below_one(self, client: FlaskClient[Any]) -> None:
        self._assert_400_field(_post(client, contracts=0), 'contracts')

    def test_negative_entry_price(self, client: FlaskClient[Any]) -> None:
        self._assert_400_field(_post(client, entry_price=-1), 'entry_price')

    def test_missing_exit_price(self, client: FlaskClient[Any]) -> None:
        payload = _valid_payload()
        del payload['exit_price']
        self._assert_400_field(client.post('/api/trades', json=payload), 'exit_price')

    def test_exit_before_entry(self, client: FlaskClient[Any]) -> None:
        response = _post(
            client,
            entry_at='2026-07-19T14:05:00Z',
            exit_at='2026-07-19T13:30:00Z',
        )
        assert response.status_code == 400

    def test_bad_side(self, client: FlaskClient[Any]) -> None:
        self._assert_400_field(_post(client, side='sideways'), 'side')

    def test_empty_symbol(self, client: FlaskClient[Any]) -> None:
        self._assert_400_field(_post(client, symbol='   '), 'symbol')


class TestErrorHandlers:
    """Content-negotiated error handling (retained from the game scaffold)."""

    def test_404_html(self, client: FlaskClient[Any]) -> None:
        response = client.get('/nonexistent')
        assert response.status_code == 404
        assert b'Page Not Found' in response.data or b'404' in response.data

    def test_404_json(self, client: FlaskClient[Any]) -> None:
        response = client.get('/nonexistent', headers={'Accept': 'application/json'})
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
