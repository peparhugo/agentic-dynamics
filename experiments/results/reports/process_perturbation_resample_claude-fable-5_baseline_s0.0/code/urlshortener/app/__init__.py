from flask import Flask, jsonify

from app.extensions import db, limiter
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    limiter.init_app(app)

    from app.routes import api, redirects

    app.register_blueprint(api)
    app.register_blueprint(redirects)

    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return jsonify({"error": "rate limit exceeded", "detail": str(error.description)}), 429

    with app.app_context():
        db.create_all()

    return app
