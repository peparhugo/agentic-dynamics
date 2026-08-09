from flask import Flask
from flask_jwt_extended import JWTManager
from config import Config
from app import init_app as init_db_module


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)
    JWTManager(app)
    init_db_module(app)

    with app.app_context():
        from app import init_db
        init_db()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
