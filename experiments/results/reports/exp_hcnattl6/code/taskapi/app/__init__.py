from flask import Flask
from flask_jwt_extended import JWTManager
from flask_cors import CORS

from .config import Config
from .database import get_db, close_db, init_db


def create_app(testing=False):
    app = Flask(__name__)
    app.config.from_object(Config)

    if testing:
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    CORS(app)
    JWTManager(app)

    app.teardown_appcontext(close_db)

    from .auth.routes import auth_bp
    from .tasks.routes import tasks_bp
    from .categories.routes import categories_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")
    app.register_blueprint(categories_bp, url_prefix="/api/categories")

    with app.app_context():
        init_db()

    return app
