from datetime import timedelta

from flask import Flask

from .extensions import db, jwt
from .routes.auth import auth_bp
from .routes.categories import categories_bp
from .routes.tasks import tasks_bp


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI="sqlite:///taskmanager.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY="dev-secret-change-me-in-production",
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=12),
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    jwt.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(auth_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(tasks_bp)

    @app.get("/")
    def index():
        return {"status": "ok", "service": "task-manager-api"}

    return app
