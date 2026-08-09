from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SECRET_KEY="dev-secret",
        JWT_SECRET_KEY="jwt-secret",
        JWT_ACCESS_TOKEN_EXPIRES=900,
        JWT_REFRESH_TOKEN_EXPIRES=86400,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    from .models import TokenBlocklist, User

    @jwt.token_in_blocklist_loader
    def check_revoked(jwt_header, jwt_payload):
        return db.session.query(TokenBlocklist.id).filter_by(jti=jwt_payload["jti"]).scalar() is not None

    @jwt.revoked_token_loader
    def revoked(jwt_header, jwt_payload):
        return jsonify(error="token_revoked", message="Token has been revoked"), 401

    @jwt.expired_token_loader
    def expired(jwt_header, jwt_payload):
        return jsonify(error="token_expired", message="Token has expired"), 401

    @jwt.invalid_token_loader
    def invalid(reason):
        return jsonify(error="invalid_token", message=reason), 401

    @jwt.unauthorized_loader
    def missing(reason):
        return jsonify(error="authorization_required", message=reason), 401

    from .errors import register_error_handlers
    register_error_handlers(app)

    from .auth import auth_bp
    from .items import items_bp
    app.register_blueprint(auth_bp, url_prefix="/v1/auth")
    app.register_blueprint(items_bp, url_prefix="/v1/items")

    with app.app_context():
        db.create_all()

    return app
