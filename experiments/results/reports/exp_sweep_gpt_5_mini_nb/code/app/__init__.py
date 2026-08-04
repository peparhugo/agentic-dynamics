from flask import Flask
from .extensions import db
from .views import v1


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=test_config.get('SECRET_KEY') if test_config else 'dev-secret',
        SQLALCHEMY_DATABASE_URI=(test_config.get('DATABASE_URI') if test_config else 'sqlite:///:memory:'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_ACCESS_EXPIRES=900,  # 15 minutes
        JWT_REFRESH_EXPIRES=604800,  # 7 days
        RATE_LIMIT_LOGIN_PER_MINUTE=5,
    )

    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    app.register_blueprint(v1, url_prefix='/v1')

    return app
