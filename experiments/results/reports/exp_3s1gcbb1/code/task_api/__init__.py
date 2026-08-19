import os

from flask import Flask, jsonify

from . import db
from .errors import ApiError
from .migrations import apply_migrations


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get(
            "TASK_API_DATABASE",
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data",
                "tasks.db",
            ),
        ),
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    db_dir = os.path.dirname(app.config["DATABASE"])
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    apply_migrations(app)

    from .routes import api

    app.register_blueprint(api, url_prefix="/api")

    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return jsonify({"error": err.message}), err.status_code

    @app.errorhandler(404)
    def handle_not_found(err):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(err):
        return jsonify({"error": "method not allowed"}), 405

    @app.errorhandler(500)
    def handle_internal_error(err):
        return jsonify({"error": "internal server error"}), 500

    return app
