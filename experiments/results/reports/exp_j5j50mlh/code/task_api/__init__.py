from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from . import db
from .routes import api


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "tasks.sqlite"),
        JSON_SORT_KEYS=False,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.register_blueprint(api)
    db.init_app(app)

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        return jsonify(error={"code": error.name, "message": error.description}), error.code

    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify(error={"code": "Not Found", "message": "The requested resource was not found."}), 404

    if app.config.get("AUTO_MIGRATE", True):
        with app.app_context():
            db.migrate()

    return app
