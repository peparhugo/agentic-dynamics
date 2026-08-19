"""Task management API package."""

from __future__ import annotations

import os

from flask import Flask

from . import db


def create_app(test_config: dict | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app.config.from_mapping(
        DATABASE=os.path.join(base_dir, "tasks.db"),
        MIGRATIONS_DIR=os.path.join(base_dir, "migrations"),
        JSON_SORT_KEYS=False,
    )

    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(db.close_db)

    from . import routes

    app.register_blueprint(routes.bp)

    with app.app_context():
        db.init_db()

    return app
