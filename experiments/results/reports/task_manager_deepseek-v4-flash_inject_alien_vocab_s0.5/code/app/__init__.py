import os

from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_jwt_extended.exceptions import (
    CSRFError,
    InvalidHeaderError,
    JWTExtendedException,
    NoAuthorizationError,
    RevokedTokenError,
    WrongTokenError,
)

from app.auth import bp as auth_bp
from app.categories import bp as categories_bp
from app.tasks import bp as tasks_bp
from app.db import close_db, run_migrations


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key"),
        DATABASE=os.environ.get("DATABASE", os.path.join(app.instance_path, "tasks.sqlite")),
        JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-key"),
        JWT_ACCESS_TOKEN_EXPIRES=int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES", 3600)),
        JWT_REFRESH_TOKEN_EXPIRES=int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRES", 2592000)),
        JWT_TOKEN_LOCATION=["headers"],
        JWT_HEADER_NAME="Authorization",
        JWT_HEADER_TYPE="Bearer",
        PASSWORD_MIN_LENGTH=int(os.environ.get("PASSWORD_MIN_LENGTH", 6)),
    )

    if test_config is not None:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    JWTManager(app)

    app.teardown_appcontext(close_db)

    app.register_blueprint(auth_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(tasks_bp)

    run_migrations(app)

    jwt = JWTManager(app)

    @jwt.unauthorized_loader
    def _unauthorized(_reason):
        return jsonify({"error": "missing or invalid authorization"}), 401

    @jwt.invalid_token_loader
    def _invalid_token(_reason):
        return jsonify({"error": "invalid token"}), 401

    @jwt.expired_token_loader
    def _expired_token(_jwt_header, _jwt_payload):
        return jsonify({"error": "token has expired"}), 401

    @jwt.revoked_token_loader
    def _revoked_token(_jwt_header, _jwt_payload):
        return jsonify({"error": "token has been revoked"}), 401

    @jwt.needs_fresh_token_loader
    def _needs_fresh(_jwt_header, _jwt_payload):
        return jsonify({"error": "fresh token required"}), 401

    @app.errorhandler(NoAuthorizationError)
    @app.errorhandler(InvalidHeaderError)
    @app.errorhandler(WrongTokenError)
    @app.errorhandler(RevokedTokenError)
    @app.errorhandler(CSRFError)
    @app.errorhandler(JWTExtendedException)
    def _jwt_error(_e):
        return jsonify({"error": "authentication failed"}), 401

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "Not Found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_e):
        return jsonify({"error": "Method Not Allowed"}), 405

    @app.errorhandler(500)
    def server_error(_e):
        return jsonify({"error": "Internal Server Error"}), 500

    return app
