from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app(config_object=None):
    app = Flask(__name__)
    if config_object is None:
        from app.config import Config
        config_object = Config
    app.config.from_object(config_object)
    db.init_app(app)

    from app.models import User, RefreshToken, AuditLog
    from app.routes import bp as v1_bp
    app.register_blueprint(v1_bp, url_prefix="/v1")

    with app.app_context():
        db.create_all()

    return app
