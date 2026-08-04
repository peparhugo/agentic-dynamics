from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, request

from .config import Config, TestConfig
from .extensions import jwt, limiter
from .routes_v1 import v1_bp


def _configure_logging(app: Flask) -> None:
    # Application log (console) is handled by Flask; here we set up audit logging to file
    log_dir = app.config.get("LOG_DIR", os.path.join(app.root_path, "..", "logs"))
    os.makedirs(log_dir, exist_ok=True)
    audit_path = os.path.join(log_dir, "audit.log")

    handler = RotatingFileHandler(audit_path, maxBytes=512_000, backupCount=3)
    handler.setLevel(logging.INFO)
    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)s user=%(user)s ip=%(ip)s method=%(method)s path=%(path)s status=%(status)s msg=%(message)s"
    )
    handler.setFormatter(fmt)

    audit_logger = logging.getLogger("audit")
    audit_logger.handlers = []  # avoid duplicate handlers on reinit
    audit_logger.propagate = False
    audit_logger.setLevel(logging.INFO)
    audit_logger.addHandler(handler)


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "bad_request", "message": str(e.description or "Bad request")}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "unauthorized", "message": str(e.description or "Unauthorized")}), 401

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not_found", "message": "Resource not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "method_not_allowed", "message": "Method not allowed"}), 405

    @app.errorhandler(429)
    def ratelimit_exceeded(e):
        return jsonify({"error": "rate_limited", "message": str(getattr(e, 'description', 'Too many requests'))}), 429

    @app.errorhandler(422)
    def unprocessable(e):
        return jsonify({"error": "validation_error", "message": getattr(e, "data", None) or str(e)}), 422

    @app.errorhandler(Exception)
    def internal_error(e):
        # Avoid leaking internal details
        app.logger.exception("Unhandled exception")
        return jsonify({"error": "internal_error", "message": "Internal server error"}), 500


def create_app(testing: bool = False) -> Flask:
    app = Flask(__name__)
    app.config.from_object(TestConfig if testing else Config)

    # Initialize extensions
    jwt.init_app(app)

    # Limiter: note that we bind on app to reset state per app instance (useful for tests)
    limiter.init_app(app)

    # Simple in-memory store for demo purposes; reset on app creation
    app.items_store = {}
    app.next_id = 1

    # Register blueprints
    app.register_blueprint(v1_bp, url_prefix="/api/v1")

    _register_error_handlers(app)
    _configure_logging(app)

    @app.after_request
    def audit_log(response):
        # Audit log minimal PII: user id (if any), ip, method, path, status
        from flask_jwt_extended import get_jwt, verify_jwt_in_request
        user = "anonymous"
        try:
            verify_jwt_in_request(optional=True)
            claims = get_jwt()
            if claims and "sub" in claims:
                user = str(claims.get("sub"))
        except Exception:
            # Ignore any JWT validation issues; we just want to log if present
            pass

        record_extras = {
            "user": user,
            "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
        }
        logging.getLogger("audit").info("request", extra=record_extras)
        return response

    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    return app
