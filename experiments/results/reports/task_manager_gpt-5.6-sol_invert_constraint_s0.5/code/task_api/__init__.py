import os

from flask import Flask, jsonify

from .extensions import db, jwt, migrate


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///tasks.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY", "development-only-change-me"),
        JWT_ACCESS_TOKEN_EXPIRES=3600,
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    from .routes import api

    app.register_blueprint(api, url_prefix="/api")

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error="Not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify(error="Method not allowed"), 405

    return app
