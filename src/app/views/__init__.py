"""Views (routes) package.

Blueprint registration for all application routes.
Each view module defines a Blueprint with its routes.
"""
from flask import Flask


def register_blueprints(app: Flask) -> None:
    """Register all blueprints with the Flask application.

    Args:
        app: Flask application instance
    """
    from .journal import journal_bp
    from .sync import attach_test_routes, sync_bp

    app.register_blueprint(journal_bp)
    app.register_blueprint(sync_bp)

    # The test-ingest route lets E2E/integration tests drive the real pipeline
    # deterministically; it is genuinely absent (404) outside TESTING/DEBUG.
    if app.config.get('TESTING') or app.config.get('DEBUG'):
        attach_test_routes(app)
