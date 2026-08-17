import os

from flask import Flask, jsonify

from app.extensions import db, migrate, jwt
from config import config_by_name


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    from app.auth.routes import auth_bp
    from app.categories.routes import categories_bp
    from app.tasks.routes import tasks_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(categories_bp, url_prefix="/api/categories")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")

    register_error_handlers(app)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"}), 200

    return app


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request"}), 400

    @jwt.unauthorized_loader
    def unauthorized_callback(reason):
        return jsonify({"error": "Missing or invalid authorization token"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        return jsonify({"error": "Invalid token"}), 422

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Token has expired"}), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Token has been revoked"}), 401
