from flask import Flask

from .config import Config
from .middleware.error_handler import register_error_handlers
from .routes.v1.auth import v1_auth_bp
from .routes.v1.users import v1_users_bp
from .routes.v2.auth import v2_auth_bp
from .routes.v2.users import v2_users_bp


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(config or Config)

    register_error_handlers(app)

    v1_bp = _build_version_blueprint("v1", v1_auth_bp, v1_users_bp)
    v2_bp = _build_version_blueprint("v2", v2_auth_bp, v2_users_bp)

    app.register_blueprint(v1_bp)
    app.register_blueprint(v2_bp)

    return app


def _build_version_blueprint(version, auth_bp, users_bp):
    from flask import Blueprint
    bp = Blueprint(f"api_{version}", __name__, url_prefix=f"/api/{version}")
    bp.register_blueprint(auth_bp, url_prefix="/auth")
    bp.register_blueprint(users_bp, url_prefix="/users")
    return bp
