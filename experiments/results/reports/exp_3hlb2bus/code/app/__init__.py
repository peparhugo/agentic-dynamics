"""Task Management API application factory."""
from flask import Flask, jsonify

from . import auth, categories, db, errors, tasks
from .config import Config


def create_app(config_object=Config, **overrides):
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.config.update(overrides)

    db.init_app(app)
    errors.init_app(app)

    app.register_blueprint(auth.bp)
    app.register_blueprint(categories.bp)
    app.register_blueprint(tasks.bp)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    return app
