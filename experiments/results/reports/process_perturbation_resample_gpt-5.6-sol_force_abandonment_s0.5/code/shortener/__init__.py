import hashlib
import math
import os
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, jsonify, redirect, request, url_for

from .storage import Storage


def _valid_url(value: object) -> bool:
    if not isinstance(value, str) or not value or len(value) > 2048:
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname)
    except ValueError:
        return False


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "shortener.sqlite3"),
        RATE_LIMIT=60,
        RATE_LIMIT_WINDOW=60,
        RATE_LIMIT_SALT="url-shortener-rate-limit",
        TRUST_PROXY=False,
    )
    if config:
        app.config.update(config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    storage = Storage(app.config["DATABASE"])
    storage.initialize()
    app.extensions["shortener_storage"] = storage

    @app.before_request
    def enforce_rate_limit():
        if request.endpoint == "health":
            return None

        address = request.remote_addr or "unknown"
        if app.config["TRUST_PROXY"]:
            address = request.headers.get("X-Forwarded-For", address).split(",", 1)[0].strip()
        client_key = hashlib.sha256(
            f"{app.config['RATE_LIMIT_SALT']}:{address}".encode()
        ).hexdigest()
        allowed, remaining, retry_after = storage.check_rate_limit(
            client_key,
            int(app.config["RATE_LIMIT"]),
            int(app.config["RATE_LIMIT_WINDOW"]),
        )
        if not allowed:
            response = jsonify(error="rate limit exceeded")
            response.status_code = 429
            response.headers["Retry-After"] = str(math.ceil(retry_after))
            response.headers["X-RateLimit-Remaining"] = "0"
            return response
        request.rate_limit_remaining = remaining
        return None

    @app.after_request
    def add_rate_limit_header(response):
        if hasattr(request, "rate_limit_remaining"):
            response.headers["X-RateLimit-Remaining"] = str(request.rate_limit_remaining)
        return response

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.post("/api/urls")
    def create_short_url():
        payload = request.get_json(silent=True)
        destination = payload.get("url") if isinstance(payload, dict) else None
        if not _valid_url(destination):
            return jsonify(error="url must be a valid http or https URL"), 400

        item = storage.create_url(destination)
        body = _url_response(item)
        response = jsonify(body)
        response.status_code = 201
        response.headers["Location"] = body["short_url"]
        return response

    @app.get("/api/urls/<code>")
    def url_analytics(code: str):
        item = storage.get_analytics(code)
        if item is None:
            return jsonify(error="short URL not found"), 404
        result = _url_response(item)
        result.update(
            click_count=item["click_count"],
            unique_visitors=item["unique_visitors"],
            last_clicked_at=item["last_clicked_at"],
            recent_clicks=item["recent_clicks"],
        )
        return jsonify(result)

    @app.get("/<code>")
    def follow(code: str):
        address = request.remote_addr or "unknown"
        visitor_hash = hashlib.sha256(
            f"{app.config['RATE_LIMIT_SALT']}:{address}".encode()
        ).hexdigest()
        destination = storage.record_click(
            code,
            visitor_hash,
            request.referrer,
            request.user_agent.string[:512],
        )
        if destination is None:
            return jsonify(error="short URL not found"), 404
        return redirect(destination, code=302)

    def _url_response(item: dict) -> dict:
        return {
            "code": item["code"],
            "url": item["url"],
            "short_url": url_for("follow", code=item["code"], _external=True),
            "created_at": item["created_at"],
        }

    return app
