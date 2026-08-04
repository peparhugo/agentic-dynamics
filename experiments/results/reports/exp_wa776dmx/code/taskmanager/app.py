from flask import Flask
from flask_cors import CORS

from .config import Config
from .models import db
from .auth import jwt
from .routes.auth import auth_bp
from .routes.tasks import tasks_bp
from .routes.categories import categories_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    jwt.init_app(app)
    CORS(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(categories_bp)

    with app.app_context():
        db.create_all()

    return app
