from flask import Flask, jsonify
from app.config import Config
from app.models import db
from app.auth.jwt import jwt
from app.middleware.rate_limiter import limiter
from app.middleware.audit import register_audit_logging
from app.utils.errors import register_error_handlers, NotFound


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    register_error_handlers(app)
    register_audit_logging(app)

    from app.routes.auth import auth_bp
    from app.routes.v1.items import v1_bp
    from app.routes.v2.items import v2_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(v1_bp)
    app.register_blueprint(v2_bp)

    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        from app.models import User
        identity = jwt_data["sub"]
        return User.query.filter_by(id=int(identity)).one_or_none()

    @jwt.unauthorized_loader
    def unauthorized_callback(reason):
        return jsonify({"error": "Missing or invalid token", "status_code": 401}), 401

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

    @app.route("/")
    def index():
        return jsonify({
            "name": "Flask REST API",
            "versions": ["v1", "v2"],
        })

    with app.app_context():
        db.create_all()

    return app
