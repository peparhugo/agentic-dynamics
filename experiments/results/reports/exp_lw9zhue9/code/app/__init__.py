import os
from flask import Flask, jsonify, request
from .logging import init_audit_logger, audit_log_request
from .routes_v1 import v1_bp


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)

    # Basic configuration
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-key"),
        JWT_ALGORITHM="HS256",
        RATE_LIMIT_PER_WINDOW=100,  # requests
        RATE_LIMIT_WINDOW_SECONDS=60,  # seconds
        PAGINATION_DEFAULT_LIMIT=10,
        PAGINATION_MAX_LIMIT=100,
        AUDIT_LOG_PATH=os.getenv("AUDIT_LOG_PATH", "logs/audit.log"),
    )

    if test_config:
        app.config.update(test_config)

    # Initialize audit logger
    init_audit_logger(app)

    # Blueprints (API versioning)
    app.register_blueprint(v1_bp, url_prefix="/api/v1")

    # Error handlers return JSON consistently
    @app.errorhandler(400)
    def bad_request(err):
        return jsonify({"error": "bad_request", "message": getattr(err, "description", "Bad request")}), 400

    @app.errorhandler(401)
    def unauthorized(err):
        return jsonify({"error": "unauthorized", "message": getattr(err, "description", "Unauthorized")}), 401

    @app.errorhandler(404)
    def not_found(err):
        return jsonify({"error": "not_found", "message": "Not found"}), 404

    @app.errorhandler(429)
    def too_many_requests(err):
        reset = getattr(err, "reset", None)
        resp = jsonify({"error": "rate_limited", "message": getattr(err, "description", "Too many requests")})
        if reset is not None:
            resp.headers["X-RateLimit-Reset"] = str(reset)
        return resp, 429

    @app.errorhandler(500)
    def server_error(err):
        return jsonify({"error": "server_error", "message": "Internal server error"}), 500

    # Audit log per request
    @app.after_request
    def after(resp):
        try:
            audit_log_request(app, request, resp)
        finally:
            return resp

    # Simple index
    @app.get("/")
    def index():
        return jsonify({"status": "ok"})

    return app
