from flask import Flask
from flask_migrate import Migrate

from .config import Config
from .extensions import db, jwt

migrate = Migrate()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    from .auth import auth_bp
    from .errors import register_error_handlers
    from .tasks import tasks_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(tasks_bp, url_prefix="/tasks")
    register_error_handlers(app)

    return app
