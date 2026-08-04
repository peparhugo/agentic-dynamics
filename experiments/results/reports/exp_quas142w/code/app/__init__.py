from flask import Flask
from app.config import Config, TestConfig
from app.extensions import db, jwt, limiter
from app.routes import v1_bp, v2_bp
from app.middleware import init_limiter, register_error_handlers
from app.utils import setup_audit_logger


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    jwt.init_app(app)
    init_limiter(app)

    setup_audit_logger(app)
    register_error_handlers(app)

    app.register_blueprint(v1_bp)
    app.register_blueprint(v2_bp)

    with app.app_context():
        from app.models.user import User
        db.create_all()

        if User.query.count() == 0:
            _seed_data(app)

    return app


def _seed_data(app):
    from werkzeug.security import generate_password_hash
    from app.models.user import User

    admin = User(
        username="admin",
        email="admin@example.com",
        password_hash=generate_password_hash("adminpass123"),
    )
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=generate_password_hash("testpass123"),
    )
    db.session.add_all([admin, user])
    db.session.commit()
    app.logger.info("Seeded initial users")
