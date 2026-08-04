import os
from datetime import timedelta

from flask import Flask, jsonify
from flask_jwt_extended.exceptions import JWTExtendedException
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from .audit import audit_bp
from .auth import auth_bp
from .extensions import db, jwt
from .items import items_bp
from .rate_limit import login_limiter
from .validation import ValidationError


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///api.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY", "development-only-change-me"),
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(minutes=15),
        JWT_REFRESH_TOKEN_EXPIRES=timedelta(days=30),
        LOGIN_RATE_LIMIT_ENABLED=True,
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    jwt.init_app(app)
    login_limiter.init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(audit_bp)
    register_error_handlers(app)

    @app.get("/v1/health")
    def health():
        return jsonify(status="ok")

    return app


def register_error_handlers(app):
    @app.errorhandler(ValidationError)
    def validation_error(error):
        return (
            jsonify(
                error={
                    "code": "validation_error",
                    "message": "Invalid request data",
                    "details": error.errors,
                }
            ),
            400,
        )

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error={"code": error.name.lower().replace(" ", "_"), "message": error.description}), error.code

    @app.errorhandler(JWTExtendedException)
    def jwt_error(error):
        return jsonify(error={"code": "unauthorized", "message": str(error)}), 401

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        app.logger.exception("Database operation failed")
        return jsonify(error={"code": "database_error", "message": "Database operation failed"}), 500

    @app.errorhandler(Exception)
    def unexpected_error(error):
        app.logger.exception("Unhandled exception")
        return jsonify(error={"code": "internal_server_error", "message": "An unexpected error occurred"}), 500

    @jwt.unauthorized_loader
    def missing_token(reason):
        return jsonify(error={"code": "unauthorized", "message": reason}), 401

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return jsonify(error={"code": "invalid_token", "message": reason}), 422

    @jwt.expired_token_loader
    def expired_token(_header, _payload):
        return jsonify(error={"code": "token_expired", "message": "Token has expired"}), 401

    @jwt.needs_fresh_token_loader
    def fresh_token_required(_header, _payload):
        return jsonify(error={"code": "fresh_token_required", "message": "A fresh token is required"}), 401

    @jwt.revoked_token_loader
    def revoked_token(_header, _payload):
        return jsonify(error={"code": "token_revoked", "message": "Token has been revoked"}), 401
