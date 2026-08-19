import os

from flask import Flask

from .auth import bp as auth_bp
from .config import Config
from .db import get_db, init_db
from .errors import register_error_handlers
from .tasks import bp as tasks_bp
from .users import bp as users_bp


def create_app(config_class=Config, **overrides):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config.update(overrides)

    app.config.setdefault("SECRET_KEY", os.environ.get("SECRET_KEY", "dev-secret-change-me"))
    app.config.setdefault("DATABASE", os.path.join(app.instance_path, "tasks.db"))
    app.config.setdefault("JWT_EXPIRATION_HOURS", 24)
    app.config.setdefault("PAGINATION_DEFAULT_PER_PAGE", 10)
    app.config.setdefault("PAGINATION_MAX_PER_PAGE", 100)

    os.makedirs(app.instance_path, exist_ok=True)

    init_db(app)

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(tasks_bp, url_prefix="/api")
    app.register_blueprint(users_bp, url_prefix="/api")

    register_error_handlers(app)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    with app.app_context():
        get_db()

    return app
