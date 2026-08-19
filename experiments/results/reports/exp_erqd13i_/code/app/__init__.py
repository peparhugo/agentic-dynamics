"""Task management API application factory."""

from __future__ import annotations

import os

from flask import Flask, jsonify

from .db import init_app
from .routes import tasks


def create_app(test_config: dict | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "tasks.sqlite"),
        TESTING=False,
    )

    if test_config is not None:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    init_app(app)
    app.register_blueprint(tasks)

    @app.get("/health")
    def health() -> tuple[dict, int]:
        return {"status": "ok"}, 200

    @app.errorhandler(404)
    def not_found(_error: object) -> tuple[object, int]:
        return jsonify({"error": "Not found"}), 404

    return app
