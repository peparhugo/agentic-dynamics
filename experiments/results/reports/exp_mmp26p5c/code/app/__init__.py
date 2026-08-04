from flask import Flask
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
jwt = JWTManager()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per minute", "60 per second"],
)


def create_app(config_object="app.config.Config"):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    from app.models import AuditLog

    def _log_audit_entry(action, resource, resource_id=None, user_id=None, details=None, status_code=None):
        from flask import request as flask_request

        try:
            entry = AuditLog(
                user_id=user_id,
                action=action,
                resource=resource,
                resource_id=resource_id,
                ip_address=flask_request.remote_addr,
                details=details,
                status_code=status_code,
            )
            db.session.add(entry)
            db.session.commit()
        except Exception:
            db.session.rollback()

    app.log_audit = _log_audit_entry

    from app.middleware.error_handlers import register_error_handlers

    register_error_handlers(app)

    from app.auth.routes import auth_bp
    from app.api.v1.items import items_bp
    from app.api.v1.users import users_bp

    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(items_bp, url_prefix="/api/v1/items")
    app.register_blueprint(users_bp, url_prefix="/api/v1/users")

    with app.app_context():
        db.create_all()

    return app
