import os

from flask import Flask, jsonify, redirect, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy.exc import IntegrityError

from .models import ClickEvent, ShortURL, db
from .utils import generate_short_code, validate_url

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "shortener.db")

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
)


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.setdefault("SQLALCHEMY_DATABASE_URI", "sqlite:///" + DEFAULT_DB_PATH)
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("SHORT_CODE_LENGTH", 6)
    app.config.setdefault("RATELIMIT_ENABLED", True)
    app.config.setdefault("RATELIMIT_STORAGE_URI", "memory://")
    if config:
        app.config.update(config)

    db.init_app(app)
    limiter.init_app(app)

    with app.app_context():
        db.create_all()

    @app.errorhandler(429)
    def ratelimit_error(e):
        return jsonify({"error": "rate limit exceeded"}), 429

    @app.post("/api/shorten")
    @limiter.limit(app.config.get("SHORTEN_RATE_LIMIT", "5 per minute"))
    def shorten():
        data = request.get_json(silent=True) or {}
        url = data.get("url")
        if not validate_url(url):
            return jsonify({"error": "a valid http(s) URL is required"}), 400

        length = app.config["SHORT_CODE_LENGTH"]
        for _ in range(10):
            code = generate_short_code(length)
            if ShortURL.query.filter_by(short_code=code).first() is not None:
                continue
            short = ShortURL(short_code=code, original_url=url)
            db.session.add(short)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                continue
            return (
                jsonify(
                    {
                        "short_code": code,
                        "short_url": request.url_root.rstrip("/") + "/" + code,
                        "original_url": url,
                    }
                ),
                201,
            )
        return jsonify({"error": "could not allocate a unique short code"}), 503

    @app.get("/<short_code>")
    def redirect_to_url(short_code):
        short = ShortURL.query.filter_by(short_code=short_code).first()
        if short is None:
            return jsonify({"error": "short code not found"}), 404

        from datetime import datetime, timezone

        short.clicks += 1
        short.last_accessed_at = datetime.now(timezone.utc)
        db.session.add(
            ClickEvent(
                short_url_id=short.id,
                referrer=request.referrer,
                user_agent=request.user_agent.string[:255],
                ip_address=request.remote_addr,
            )
        )
        db.session.commit()
        return redirect(short.original_url, code=302)

    @app.get("/api/stats/<short_code>")
    def stats(short_code):
        short = ShortURL.query.filter_by(short_code=short_code).first()
        if short is None:
            return jsonify({"error": "short code not found"}), 404

        recent = (
            short.click_events.order_by(ClickEvent.timestamp.desc())
            .limit(10)
            .all()
        )
        return jsonify(
            {
                "short_code": short.short_code,
                "original_url": short.original_url,
                "created_at": short.created_at.isoformat() if short.created_at else None,
                "clicks": short.clicks,
                "last_accessed_at": (
                    short.last_accessed_at.isoformat()
                    if short.last_accessed_at
                    else None
                ),
                "recent_clicks": [c.to_dict() for c in recent],
            }
        )

    @app.get("/api/urls")
    def list_urls():
        shorts = ShortURL.query.order_by(ShortURL.created_at.desc()).all()
        return jsonify({"urls": [s.to_dict() for s in shorts]})

    return app
