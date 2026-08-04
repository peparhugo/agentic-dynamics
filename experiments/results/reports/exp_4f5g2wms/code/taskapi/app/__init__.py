from flask import Flask

from app.config import Config
from app.database import init_db, close_db


def create_app(config=None):
    app = Flask(__name__)
    if config is None:
        app.config.from_object(Config)
    else:
        app.config.update(config)

    init_db(app)
    app.teardown_appcontext(close_db)

    from app.routes.auth import auth_bp
    from app.routes.tasks import tasks_bp
    from app.routes.categories import categories_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(tasks_bp, url_prefix="/tasks")
    app.register_blueprint(categories_bp, url_prefix="/categories")

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app
