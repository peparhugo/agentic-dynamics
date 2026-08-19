from flask import Flask
from flask_jwt_extended import JWTManager

from .config import get_config
from .db import init_app as init_db_app
from .db import init_db


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(get_config())
    if config:
        app.config.update(config)

    init_db(app.config["DATABASE"])
    init_db_app(app)

    jwt = JWTManager(app)

    @jwt.unauthorized_loader
    @jwt.invalid_token_loader
    @jwt.expired_token_loader
    @jwt.needs_fresh_token_loader
    @jwt.revoked_token_loader
    def _jwt_error(*_args):
        return {"error": "invalid or missing token"}, 401

    from . import auth, categories, priorities, tasks

    app.register_blueprint(auth.bp)
    app.register_blueprint(tasks.bp)
    app.register_blueprint(categories.bp)
    app.register_blueprint(priorities.bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.errorhandler(404)
    def not_found(_):
        return {"error": "not found"}, 404

    @app.errorhandler(405)
    def method_not_allowed(_):
        return {"error": "method not allowed"}, 405

    @app.errorhandler(500)
    def internal_error(_):
        return {"error": "internal server error"}, 500

    return app
