import os

from flask import Flask, jsonify

from config import config_by_name


def create_app(config_name=None, test_overrides=None):
    app = Flask(__name__, instance_relative_config=True)

    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app.config.from_object(config_by_name[config_name])

    if test_overrides:
        app.config.update(test_overrides)

    os.makedirs(os.path.dirname(app.config["DATABASE"]) or ".", exist_ok=True)

    from . import db

    db.init_app(app)

    from .errors import register_error_handlers

    register_error_handlers(app)

    from .routes.projects import projects_bp
    from .routes.tasks import tasks_bp

    app.register_blueprint(projects_bp)
    app.register_blueprint(tasks_bp)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    with app.app_context():
        db.init_db()

    return app
