from flask import Flask
from flask_jwt_extended import JWTManager
from config import Config
from models import db
from auth import auth_bp
from tasks import tasks_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    JWTManager(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
