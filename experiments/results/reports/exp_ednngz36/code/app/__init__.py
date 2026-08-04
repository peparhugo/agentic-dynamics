"""Application factory."""
from flask import Flask, jsonify

from .config import Config
from .errors import register_error_handlers
from .rate_limit import RateLimiter, install_rate_limiting
from .storage import Store

API_VERSIONS = ["v1"]


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    app.extensions["store"] = Store()
    app.extensions["rate_limiter"] = RateLimiter()

    register_error_handlers(app)
    install_rate_limiting(app, app.extensions["rate_limiter"])

    from .api.v1 import bp as v1_bp
    app.register_blueprint(v1_bp, url_prefix="/api/v1")

    @app.get("/api")
    def api_index():
        return jsonify({
            "versions": [
                {"version": v, "url": f"/api/{v}", "status": "stable"}
                for v in API_VERSIONS
            ],
            "latest": API_VERSIONS[-1],
        })

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    return app
