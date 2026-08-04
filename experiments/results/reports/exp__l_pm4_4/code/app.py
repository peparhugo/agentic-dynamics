from __future__ import annotations

import hashlib
import secrets
import sqlite3
import string
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from flask import Flask, current_app, g, jsonify, redirect, request, url_for


ALPHABET = string.ascii_letters + string.digits
SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    code TEXT PRIMARY KEY,
    original_url TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL REFERENCES urls(code) ON DELETE CASCADE,
    clicked_at TEXT NOT NULL,
    referrer TEXT,
    user_agent TEXT,
    visitor_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_clicks_code_time ON clicks(code, clicked_at);
"""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FixedWindowRateLimiter:
    """Small in-process limiter suitable for a single application instance."""

    def __init__(self, limit: int, window_seconds: int, clock: Callable[[], float] = time.time):
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self._clients: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()

    def consume(self, client: str) -> tuple[bool, int, int]:
        now = int(self.clock())
        window = now // self.window_seconds
        with self._lock:
            current_window, count = self._clients.get(client, (window, 0))
            if current_window != window:
                current_window, count = window, 0
            allowed = count < self.limit
            if allowed:
                count += 1
            self._clients[client] = (current_window, count)
        remaining = max(0, self.limit - count)
        retry_after = (window + 1) * self.window_seconds - now
        return allowed, remaining, retry_after


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=str(Path(app.instance_path) / "shortener.sqlite3"),
        CODE_LENGTH=8,
        CODE_ATTEMPTS=10,
        RATE_LIMIT=30,
        RATE_WINDOW_SECONDS=60,
        NOW=utc_now,
        CODE_GENERATOR=None,
    )
    if config:
        app.config.update(config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.executescript(SCHEMA)

    app.extensions["rate_limiter"] = FixedWindowRateLimiter(
        app.config["RATE_LIMIT"], app.config["RATE_WINDOW_SECONDS"], app.config.get("RATE_CLOCK", time.time)
    )

    app.teardown_appcontext(close_database)
    register_routes(app)
    return app


def get_database() -> sqlite3.Connection:
    if "database" not in g:
        g.database = sqlite3.connect(current_app.config["DATABASE"], timeout=5)
        g.database.row_factory = sqlite3.Row
        g.database.execute("PRAGMA foreign_keys = ON")
        g.database.execute("PRAGMA busy_timeout = 5000")
    return g.database


def close_database(_error: BaseException | None = None) -> None:
    database = g.pop("database", None)
    if database is not None:
        database.close()


def iso_now() -> str:
    return current_app.config["NOW"]().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def valid_url(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 4096 or any(ord(char) < 32 for char in value):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and parsed.username is None
    except ValueError:
        return False


def generate_code() -> str:
    generator = current_app.config.get("CODE_GENERATOR")
    if generator:
        return generator()
    return "".join(secrets.choice(ALPHABET) for _ in range(current_app.config["CODE_LENGTH"]))


def register_routes(app: Flask) -> None:
    @app.post("/api/urls")
    def create_short_url():
        client = request.remote_addr or "unknown"
        allowed, remaining, retry_after = app.extensions["rate_limiter"].consume(client)
        if not allowed:
            response = jsonify(error="rate limit exceeded")
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            response.headers["X-RateLimit-Remaining"] = "0"
            return response

        payload = request.get_json(silent=True)
        original_url = payload.get("url") if isinstance(payload, dict) else None
        if not valid_url(original_url):
            return jsonify(error="url must be a valid http or https URL"), 400

        database = get_database()
        created_at = iso_now()
        for _ in range(current_app.config["CODE_ATTEMPTS"]):
            code = generate_code()
            if not isinstance(code, str) or not code or len(code) > 128:
                continue
            try:
                database.execute(
                    "INSERT INTO urls (code, original_url, created_at) VALUES (?, ?, ?)",
                    (code, original_url, created_at),
                )
                database.commit()
                response = jsonify(
                    code=code,
                    short_url=url_for("follow_short_url", code=code, _external=True),
                    original_url=original_url,
                    created_at=created_at,
                )
                response.status_code = 201
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                return response
            except sqlite3.IntegrityError:
                database.rollback()
        return jsonify(error="could not allocate a unique short code"), 503

    @app.get("/<code>")
    def follow_short_url(code: str):
        database = get_database()
        row = database.execute("SELECT original_url FROM urls WHERE code = ?", (code,)).fetchone()
        if row is None:
            return jsonify(error="short URL not found"), 404

        visitor = request.remote_addr or "unknown"
        visitor_hash = hashlib.sha256(visitor.encode()).hexdigest()
        database.execute(
            "INSERT INTO clicks (code, clicked_at, referrer, user_agent, visitor_hash) VALUES (?, ?, ?, ?, ?)",
            (code, iso_now(), request.referrer, request.user_agent.string or None, visitor_hash),
        )
        database.commit()
        return redirect(row["original_url"], code=302)

    @app.get("/api/urls/<code>")
    def get_short_url(code: str):
        database = get_database()
        row = database.execute(
            "SELECT code, original_url, created_at FROM urls WHERE code = ?", (code,)
        ).fetchone()
        if row is None:
            return jsonify(error="short URL not found"), 404
        clicks = database.execute("SELECT COUNT(*) FROM clicks WHERE code = ?", (code,)).fetchone()[0]
        return jsonify(**dict(row), short_url=url_for("follow_short_url", code=code, _external=True), clicks=clicks)

    @app.get("/api/urls/<code>/analytics")
    def analytics(code: str):
        database = get_database()
        if database.execute("SELECT 1 FROM urls WHERE code = ?", (code,)).fetchone() is None:
            return jsonify(error="short URL not found"), 404
        rows = database.execute(
            "SELECT clicked_at, referrer, user_agent, visitor_hash FROM clicks WHERE code = ? ORDER BY id DESC",
            (code,),
        ).fetchall()
        unique_visitors = len({row["visitor_hash"] for row in rows})
        return jsonify(
            code=code,
            total_clicks=len(rows),
            unique_visitors=unique_visitors,
            clicks=[
                {"clicked_at": row["clicked_at"], "referrer": row["referrer"], "user_agent": row["user_agent"]}
                for row in rows
            ],
        )

    @app.delete("/api/urls/<code>")
    def delete_short_url(code: str):
        database = get_database()
        cursor = database.execute("DELETE FROM urls WHERE code = ?", (code,))
        database.commit()
        if cursor.rowcount == 0:
            return jsonify(error="short URL not found"), 404
        return "", 204


app = create_app()


if __name__ == "__main__":
    app.run()
