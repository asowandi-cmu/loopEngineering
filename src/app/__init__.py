"""Flask application factory and initialization."""
import os
from flask import Flask, Response
from .config import config
from .models.base import db
from .logging_config import configure_logging


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application.

    Uses the application factory pattern for flexibility in testing
    and deployment scenarios.

    Args:
        config_name: Configuration to use ('development', 'testing', 'production').
                    Defaults to FLASK_ENV environment variable or 'development'.

    Returns:
        Configured Flask application instance.
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Configure logging before other initialization
    configure_logging(app)

    # Initialize extensions
    db.init_app(app)

    # Initialize Flask-Migrate
    from flask_migrate import Migrate
    Migrate(app, db)

    # Register error handlers
    from .errors import register_error_handlers
    register_error_handlers(app)

    # Register blueprints
    from .views import register_blueprints
    register_blueprints(app)

    # Serve an inline SVG favicon so browsers' automatic /favicon.ico
    # request doesn't 404 (which the error handler logs as a warning).
    _FAVICON = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
        b'<rect width="16" height="16" rx="3" fill="#1f2937"/>'
        b'<path d="M3 11l3-3 2 2 5-5" stroke="#34d399" stroke-width="1.5" '
        b'fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )

    @app.route('/favicon.ico')
    def favicon() -> Response:
        return Response(_FAVICON, mimetype='image/svg+xml')

    return app
