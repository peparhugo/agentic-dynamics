from flask import Flask, jsonify
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from app.config import Config
from app.extensions import db, jwt, migrate


def create_app(config_class=Config, config_override=None):
    app = Flask(__name__)
    app.config.from_object(config_class)
    if config_override:
        app.config.update(config_override)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    from app.routes.auth import auth_bp
    from app.routes.meta import meta_bp
    from app.routes.tasks import tasks_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")
    app.register_blueprint(meta_bp, url_prefix="/api")

    register_jwt_handlers(app)
    register_error_handlers(app)

    return app


def register_jwt_handlers(app):
    jwt = app.extensions.get("flask-jwt-extended")

    if jwt is None:
        return

    @jwt.unauthorized_loader
    def missing_token_callback(reason):
        return jsonify({"error": "Missing authorization token."}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        return jsonify({"error": "Invalid token."}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_data):
        return jsonify({"error": "Token has expired."}), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_data):
        return jsonify({"error": "Token has been revoked."}), 401


def register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def handle_http_exception(exc):
        return jsonify({"error": exc.description or exc.name}), exc.code

    @app.errorhandler(SQLAlchemyError)
    def handle_db_error(exc):
        return jsonify({"error": "Database error."}), 500

    @app.errorhandler(Exception)
    def handle_uncaught_exception(exc):
        return jsonify({"error": "Internal server error."}), 500
