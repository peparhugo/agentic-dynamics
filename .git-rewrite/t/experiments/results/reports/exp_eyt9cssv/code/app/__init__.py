from flask import Flask

from app.config import Config
from app.extensions import db
from app.models import AuditLog, Item, User
from app.middleware.errors import register_error_handlers


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    register_error_handlers(app)

    from app.auth.routes import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.api.items import bp as items_bp
    app.register_blueprint(items_bp)

    with app.app_context():
        db.create_all()

    return app
