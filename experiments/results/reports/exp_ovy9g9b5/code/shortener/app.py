"""Flask REST API for the URL shortener.

Endpoints:
    POST   /api/shorten          -> create a short URL (rate limited)
    GET    /api/urls/<code>      -> metadata for a short URL
    GET    /api/urls/<code>/stats-> click analytics
    DELETE /api/urls/<code>      -> delete a short URL
    GET    /<code>               -> redirect to the long URL (records a click)
    GET    /healthz              -> health check
"""

from __future__ import annotations

import sqlite3
from urllib.parse import urlparse

from flask import Flask, jsonify, redirect, request

from shortener.codes import generate_unique_code, is_valid_code
from shortener.db import Database
from shortener.ratelimit import RateLimiter

MAX_URL_LENGTH = 2048


def _is_valid_url(url: str) -> bool:
    if not url or len(url) > MAX_URL_LENGTH:
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def create_app(
    db_path: str = ":memory:",
    rate_limit: int = 10,
    rate_window: float = 60.0,
) -> Flask:
    app = Flask(__name__)
    db = Database(db_path)
    limiter = RateLimiter(max_requests=rate_limit, window_seconds=rate_window)

    app.extensions["shortener_db"] = db
    app.extensions["shortener_limiter"] = limiter

    def client_key() -> str:
        return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")

    def url_payload(row: dict) -> dict:
        return {
            "code": row["code"],
            "long_url": row["long_url"],
            "created_at": row["created_at"],
            "short_url": request.host_url.rstrip("/") + "/" + row["code"],
        }

    # -- API ---------------------------------------------------------------

    @app.post("/api/shorten")
    def shorten():
        key = client_key()
        if not limiter.allow(key):
            resp = jsonify(error="rate limit exceeded")
            resp.status_code = 429
            resp.headers["Retry-After"] = str(int(limiter.window_seconds))
            return resp

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="request body must be a JSON object"), 400

        long_url = data.get("url")
        if not isinstance(long_url, str) or not _is_valid_url(long_url):
            return jsonify(error="'url' must be a valid http(s) URL"), 400

        custom = data.get("custom_code")
        if custom is not None:
            if not isinstance(custom, str) or not is_valid_code(custom):
                return jsonify(error="'custom_code' must be 1-16 base62 characters"), 400
            try:
                row = db.insert_url(custom, long_url)
            except sqlite3.IntegrityError:
                return jsonify(error="custom code already in use"), 409
            return jsonify(url_payload(row)), 201

        # Collision-resistant generation: random base62 + uniqueness check,
        # plus a retry on the DB unique constraint to close the race window.
        for _ in range(5):
            code = generate_unique_code(db.code_exists)
            try:
                row = db.insert_url(code, long_url)
            except sqlite3.IntegrityError:
                continue  # lost a race; try a fresh code
            return jsonify(url_payload(row)), 201
        return jsonify(error="could not allocate a short code"), 500

    @app.get("/api/urls/<code>")
    def get_url(code: str):
        row = db.get_url_by_code(code)
        if row is None:
            return jsonify(error="not found"), 404
        payload = url_payload(row)
        payload["clicks"] = db.click_count(row["id"])
        return jsonify(payload), 200

    @app.get("/api/urls/<code>/stats")
    def get_stats(code: str):
        row = db.get_url_by_code(code)
        if row is None:
            return jsonify(error="not found"), 404
        stats = db.click_stats(row["id"])
        stats["code"] = code
        stats["long_url"] = row["long_url"]
        return jsonify(stats), 200

    @app.delete("/api/urls/<code>")
    def delete_url(code: str):
        if not db.delete_url(code):
            return jsonify(error="not found"), 404
        return "", 204

    # -- Redirect ------------------------------------------------------------

    @app.get("/<code>")
    def follow(code: str):
        row = db.get_url_by_code(code)
        if row is None:
            return jsonify(error="not found"), 404
        db.record_click(
            row["id"],
            ip=client_key(),
            user_agent=request.headers.get("User-Agent"),
            referrer=request.headers.get("Referer"),
        )
        return redirect(row["long_url"], code=302)

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok"), 200

    return app


if __name__ == "__main__":  # pragma: no cover
    create_app("shortener.db").run(debug=True)
