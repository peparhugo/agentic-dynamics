from flask import Flask
from app.config import Config
from app.extensions import db, limiter
from app.models.user import User
from app.models.item import Item
from app.models.audit_log import AuditLog


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    limiter.init_app(app)

    from app.middleware.error_handler import errors_bp
    app.register_blueprint(errors_bp)

    from app.api.v1.auth import auth_bp
    from app.api.v1.items import items_bp
    from app.api.v1.users import users_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(users_bp)

    with app.app_context():
        db.create_all()

    return app
