from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager

db = SQLAlchemy()
jwt = JWTManager()


def create_app(config_object=None):
    app = Flask(__name__)

    if config_object is None:
        app.config.from_object("app.config.Config")
    elif isinstance(config_object, str):
        app.config.from_object(config_object)
    else:
        app.config.from_object(config_object)

    db.init_app(app)
    jwt.init_app(app)

    from app.auth import register_jwt_handlers
    register_jwt_handlers(jwt)

    from app.middleware.error_handler import register_error_handlers
    register_error_handlers(app)

    from app.middleware.rate_limit import rate_limit

    @app.before_request
    def apply_rate_limit():
        from flask import g
        g._rate_limit_disabled = False

    from app.v1.routes import users_bp, widgets_bp
    app.register_blueprint(users_bp, url_prefix="/api/v1")
    app.register_blueprint(widgets_bp, url_prefix="/api/v1/widgets")

    from app.v2.routes import widgets_v2_bp
    app.register_blueprint(widgets_v2_bp, url_prefix="/api/v2/widgets")

    @app.route("/health")
    def health():
        return {"status": "ok", "versions": ["v1", "v2"]}

    with app.app_context():
        db.create_all()

    return app
