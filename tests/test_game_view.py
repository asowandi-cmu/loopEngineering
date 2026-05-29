"""Tests for the Space Invaders game view.

The game is entirely client-side, so the backend's only responsibility is
to serve the HTML shell containing the React Island mount point. These tests
verify that contract: the homepage returns 200, advertises the correct
title, and includes the ``data-island="game"`` hook that ``main.ts`` uses
to mount the canvas game.
"""
from __future__ import annotations

import json
from typing import Any
from flask.testing import FlaskClient


class TestGamePage:
    """Tests for the main HTML page that hosts the game."""

    def test_index_returns_html(self, client: FlaskClient[Any]) -> None:
        """GET / should return a 200 HTML page."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Space Invaders' in response.data

    def test_index_contains_island_mount(self, client: FlaskClient[Any]) -> None:
        """Index page should contain the game island mount point."""
        response = client.get('/')
        assert b'data-island="game"' in response.data

    def test_index_title(self, client: FlaskClient[Any]) -> None:
        """The page <title> should advertise Space Invaders."""
        response = client.get('/')
        assert b'<title>Space Invaders</title>' in response.data


class TestErrorHandlers:
    """Tests for error handling.

    Retained from the original scaffold so that error-handler coverage
    (content negotiation between HTML and JSON) survives the Hello removal.
    """

    def test_404_html(self, client: FlaskClient[Any]) -> None:
        """404 should return HTML for browser requests."""
        response = client.get('/nonexistent')
        assert response.status_code == 404
        assert b'Page Not Found' in response.data or b'404' in response.data

    def test_404_json(self, client: FlaskClient[Any]) -> None:
        """404 should return JSON for API requests."""
        response = client.get(
            '/nonexistent',
            headers={'Accept': 'application/json'}
        )
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
