from flask import Flask

from app.config import Config
from app.extensions import db, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    from app.auth import auth_bp
    from app.categories import categories_bp
    from app.tasks import tasks_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(tasks_bp, url_prefix="/api")
    app.register_blueprint(categories_bp, url_prefix="/api")

    from app import models  # noqa: F401  (ensure models are registered)

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app
