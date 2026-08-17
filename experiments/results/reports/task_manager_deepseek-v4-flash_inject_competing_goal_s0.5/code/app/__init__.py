import os

from flask import Flask, jsonify

from .config import DefaultConfig
from .db import db
from .errors import ApiError
from .migrations import run_migrations


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(DefaultConfig)
    if config:
        app.config.update(config)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.abspath(app.config["DATABASE_PATH"])

    db.init_app(app)

    with app.app_context():
        run_migrations(app.config["DATABASE_PATH"])

    from .auth import bp as auth_bp
    from .categories import bp as categories_bp
    from .tasks import bp as tasks_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(categories_bp)

    _register_handlers(app)
    return app


def _register_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(error):
        payload = {"error": error.message}
        if error.errors:
            payload["errors"] = error.errors
        return jsonify(payload), error.status_code

    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(500)
    def handle_server_error(error):
        app.logger.exception(error)
        if app.config.get("TESTING"):
            raise error
        return jsonify({"error": "internal server error"}), 500
