import os
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from contextlib import closing
from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import Flask, g, jsonify, redirect, request


SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    code TEXT PRIMARY KEY,
    target_url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    click_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL REFERENCES urls(code) ON DELETE CASCADE,
    clicked_at TEXT NOT NULL,
    referrer TEXT,
    user_agent TEXT
);
CREATE INDEX IF NOT EXISTS clicks_code_clicked_at ON clicks(code, clicked_at);
"""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class RateLimiter:
    def __init__(self, limit, window_seconds, clock=time.monotonic):
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self._requests = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key):
        now = self.clock()
        cutoff = now - self.window_seconds
        with self._lock:
            timestamps = self._requests[key]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= self.limit:
                retry_after = max(1, int(timestamps[0] + self.window_seconds - now + 0.999))
                return False, retry_after
            timestamps.append(now)
            return True, None


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("DATABASE", os.path.join(app.instance_path, "shortener.sqlite")),
        RATE_LIMIT=10,
        RATE_WINDOW_SECONDS=60,
        CODE_BYTES=6,
        CODE_RETRIES=10,
    )
    if config:
        app.config.update(config)

    os.makedirs(os.path.dirname(os.path.abspath(app.config["DATABASE"])), exist_ok=True)
    limiter = RateLimiter(app.config["RATE_LIMIT"], app.config["RATE_WINDOW_SECONDS"])
    app.extensions["rate_limiter"] = limiter

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"], timeout=5)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
            g.db.execute("PRAGMA journal_mode = WAL")
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    with closing(sqlite3.connect(app.config["DATABASE"])) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(SCHEMA)

    def url_payload(row):
        return {
            "code": row["code"],
            "short_url": request.host_url.rstrip("/") + "/" + row["code"],
            "target_url": row["target_url"],
            "created_at": row["created_at"],
            "click_count": row["click_count"],
        }

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error="not_found", message="Resource not found"), 404

    @app.post("/api/urls")
    def create_short_url():
        allowed, retry_after = limiter.check(request.remote_addr or "unknown")
        if not allowed:
            response = jsonify(error="rate_limit_exceeded", message="Too many requests")
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response

        data = request.get_json(silent=True)
        target_url = data.get("url") if isinstance(data, dict) else None
        if not isinstance(target_url, str) or not target_url.strip():
            return jsonify(error="invalid_url", message="A non-empty 'url' is required"), 400
        target_url = target_url.strip()
        parsed = urlparse(target_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return jsonify(error="invalid_url", message="Only absolute HTTP(S) URLs are supported"), 400

        db = get_db()
        created_at = utc_now()
        for _ in range(app.config["CODE_RETRIES"]):
            code = secrets.token_urlsafe(app.config["CODE_BYTES"])
            try:
                db.execute(
                    "INSERT INTO urls (code, target_url, created_at) VALUES (?, ?, ?)",
                    (code, target_url, created_at),
                )
                db.commit()
                row = db.execute("SELECT * FROM urls WHERE code = ?", (code,)).fetchone()
                return jsonify(url_payload(row)), 201
            except sqlite3.IntegrityError:
                db.rollback()
        return jsonify(error="code_generation_failed", message="Could not allocate a unique code"), 503

    @app.get("/api/urls/<code>")
    def get_short_url(code):
        row = get_db().execute("SELECT * FROM urls WHERE code = ?", (code,)).fetchone()
        if row is None:
            return not_found(None)
        return jsonify(url_payload(row))

    @app.get("/api/urls/<code>/analytics")
    def get_analytics(code):
        db = get_db()
        row = db.execute("SELECT * FROM urls WHERE code = ?", (code,)).fetchone()
        if row is None:
            return not_found(None)
        clicks = db.execute(
            "SELECT clicked_at, referrer, user_agent FROM clicks WHERE code = ? ORDER BY id DESC",
            (code,),
        ).fetchall()
        return jsonify(
            code=code,
            click_count=row["click_count"],
            clicks=[dict(click) for click in clicks],
        )

    @app.delete("/api/urls/<code>")
    def delete_short_url(code):
        db = get_db()
        cursor = db.execute("DELETE FROM urls WHERE code = ?", (code,))
        db.commit()
        if cursor.rowcount == 0:
            return not_found(None)
        return "", 204

    @app.get("/<code>")
    def follow_short_url(code):
        db = get_db()
        row = db.execute("SELECT target_url FROM urls WHERE code = ?", (code,)).fetchone()
        if row is None:
            return not_found(None)
        clicked_at = utc_now()
        with db:
            db.execute("UPDATE urls SET click_count = click_count + 1 WHERE code = ?", (code,))
            db.execute(
                "INSERT INTO clicks (code, clicked_at, referrer, user_agent) VALUES (?, ?, ?, ?)",
                (code, clicked_at, request.referrer, request.user_agent.string or None),
            )
        return redirect(row["target_url"], code=302)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
