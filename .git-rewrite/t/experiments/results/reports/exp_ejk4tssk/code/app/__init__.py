from flask import Flask
from .routes import api_bp
from .errors import register_error_handlers
from .logging_config import configure_audit_logging

def create_app():
    app = Flask(__name__)
    app.config.from_mapping({
        "JWT_SECRET": "dev-secret-change-me",
        "JWT_ALGORITHM": "HS256",
        "JWT_EXP_SECONDS": 3600,
        "RATE_LIMIT": 5,  # requests
        "RATE_PERIOD": 60,  # seconds
    })

    configure_audit_logging(app)
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    register_error_handlers(app)

    return app
