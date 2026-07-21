"""Pytest configuration and fixtures.

Provides test fixtures for the Flask application including:
- Test app with testing configuration
- Test client for making HTTP requests
- Database setup/teardown per test
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from app import create_app
from flask import Flask
from flask.testing import FlaskClient, FlaskCliRunner
from app.models import db

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture
def app() -> Iterator[Flask]:
    """Create application configured for testing.

    Uses SQLite in-memory database for fast, isolated tests.
    Yields the app within application context.
    """
    app = create_app('testing')

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app: Flask) -> FlaskClient[Any]:
    """Create test client for making HTTP requests.

    Use this fixture to test routes without running a server.
    """
    return app.test_client()


@pytest.fixture
def runner(app: Flask) -> FlaskCliRunner:
    """Create CLI runner for testing Flask commands."""
    cli_runner: FlaskCliRunner = app.test_cli_runner()
    return cli_runner


@pytest.fixture
def seeded_instruments(app: Flask) -> None:
    """Seed the default instrument tick specs within the app context."""
    from app.controllers.instrument import seed_default_instruments

    seed_default_instruments()


def load_dxtrade_fixture(name: str) -> list[dict[str, Any]]:
    """Load a recorded DXtrade fill fixture (list of normalized fill dicts)."""
    path = FIXTURES / 'dxtrade' / f'{name}.json'
    data: list[dict[str, Any]] = json.loads(path.read_text())
    return data


def load_statement(name: str) -> bytes:
    """Load a raw statement CSV fixture as bytes."""
    return (FIXTURES / 'statements' / name).read_bytes()
