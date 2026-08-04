from flask import Flask
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from .routes import api as api_blueprint
import logging

def create_app(config=None):
    app = Flask(__name__)
    # Basic config with defaults; can be overridden via config dict
    app.config.setdefault("SECRET_KEY", "change-me")
    app.config.setdefault("JWT_SECRET_KEY", "jwt-secret-key-change-me")
    app.config.setdefault("RATELIMIT_DEFAULT", "20 per minute")
    app.config.setdefault("API_TITLE", "My API");
    app.config.setdefault("API_VERSION", "v1")

    if config:
        app.config.update(config)

    # Setup extensions
    jwt = JWTManager(app)
    limiter = Limiter(
        app,
        key_func=get_remote_address,
        default_limits=[app.config.get("RATELIMIT_DEFAULT", "20 per minute")],
    )

    # Audit logger setup
    logger = logging.getLogger("audit")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    # Simple route registration for versioned API
    app.register_blueprint(api_blueprint, url_prefix="/api")

    # Expose audit logger for other modules if needed
    app.audit_logger = logger

    return app
