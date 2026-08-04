import logging
import os
import uuid
from datetime import timedelta

from flask import Flask, jsonify, g, request
from werkzeug.exceptions import HTTPException

from .extensions import jwt, limiter, ma
from .routes.auth import bp as auth_bp
from .routes.items import bp as items_bp


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)

    # Base config
    app.config.setdefault("SECRET_KEY", os.environ.get("SECRET_KEY", "dev-secret-change-me"))
    app.config.setdefault("JWT_SECRET_KEY", os.environ.get("JWT_SECRET_KEY", app.config["SECRET_KEY"]))
    app.config.setdefault("JWT_ACCESS_TOKEN_EXPIRES", timedelta(hours=1))
    app.config.setdefault("RATELIMIT_DEFAULT", "200 per hour;50 per minute")
    app.config.setdefault("RATELIMIT_STORAGE_URI", "memory://")
    app.config.setdefault("RATELIMIT_HEADERS_ENABLED", True)
    app.config.setdefault("PROPAGATE_EXCEPTIONS", False)

    if test_config:
        app.config.update(test_config)

    # Initialize extensions
    ma.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    # Blueprints (API versioned)
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(items_bp, url_prefix="/api/v1/items")

    # Health endpoint (unversioned)
    @app.get("/health")
    def health():
        return {"status": "ok"}

    # Audit logger setup
    _setup_audit_logger(app)

    @app.before_request
    def _request_context():
        # Attach a request id for tracing
        g.request_id = str(uuid.uuid4())

    @app.after_request
    def _after(resp):
        # Structured audit log after every response
        user = getattr(g, "jwt_identity", None)
        # Client IP (honor X-Forwarded-For if behind proxy, but keep it simple here)
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        app.logger.getChild("audit").info(
            "event=audit method=%s path=%s status=%s ip=%s user=%s request_id=%s",
            request.method,
            request.path,
            resp.status_code,
            ip,
            user,
            g.request_id,
        )
        # Include request id header for clients
        resp.headers["X-Request-Id"] = g.request_id
        return resp

    # Error handlers -> JSON shape
    @app.errorhandler(HTTPException)
    def handle_http_exc(e: HTTPException):
        response = {
            "error": {
                "type": e.__class__.__name__,
                "message": e.description,
            },
            "request_id": getattr(g, "request_id", None),
        }
        return jsonify(response), e.code

    @app.errorhandler(Exception)
    def handle_unexpected(e: Exception):
        app.logger.exception("Unhandled error: %s", e)
        response = {
            "error": {
                "type": e.__class__.__name__,
                "message": "Internal Server Error",
            },
            "request_id": getattr(g, "request_id", None),
        }
        return jsonify(response), 500

    return app


def _setup_audit_logger(app: Flask):
    # Dedicated audit logger under app.logger
    audit_logger = app.logger.getChild("audit")
    audit_logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if re-created (e.g., in tests)
    if not audit_logger.handlers:
        logs_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        fh = logging.FileHandler(os.path.join(logs_dir, "audit.log"))
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        fh.setFormatter(fmt)
        audit_logger.addHandler(fh)
