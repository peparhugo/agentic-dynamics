from flask import Flask, jsonify

from .config import Config
from .extensions import db


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)

    from . import models  # noqa: F401  (register models with SQLAlchemy)

    from .auth import bp as auth_bp
    from .categories import bp as categories_bp
    from .tasks import bp as tasks_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(tasks_bp)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "version": app.config["APP_VERSION"]}), 200

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not found."}), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({"error": "Method not allowed."}), 405

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "Bad request."}), 400

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return jsonify({"error": "Internal server error."}), 500

    return app
