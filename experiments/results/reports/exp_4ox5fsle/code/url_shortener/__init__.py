import secrets
import sqlite3
import string
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, current_app, g, jsonify, redirect, request, url_for


ALPHABET = string.ascii_letters + string.digits
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
CREATE INDEX IF NOT EXISTS clicks_code_time ON clicks(code, clicked_at DESC);
CREATE TABLE IF NOT EXISTS rate_limits (
    client_key TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    window_start INTEGER NOT NULL,
    request_count INTEGER NOT NULL,
    PRIMARY KEY (client_key, endpoint, window_start)
);
"""


def utc_timestamp(timestamp=None):
    value = time.time() if timestamp is None else timestamp
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def generate_code(length):
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def get_db():
    if "db" not in g:
        connection = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db():
    connection = get_db()
    connection.executescript(SCHEMA)
    connection.commit()


def json_error(message, status, **details):
    body = {"error": {"message": message, "status": status}}
    body["error"].update(details)
    return jsonify(body), status


def valid_url(value):
    if not isinstance(value, str) or not value or len(value) > 2048:
        return False
    if any(character in value for character in "\r\n\x00"):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except ValueError:
        return False


def client_key():
    # REMOTE_ADDR is used directly unless ProxyFix is deliberately configured by a deployer.
    return request.remote_addr or "unknown"


def enforce_rate_limit(endpoint):
    limit = current_app.config["RATE_LIMIT"]
    window = current_app.config["RATE_LIMIT_WINDOW"]
    if limit <= 0:
        return None

    now = int(current_app.config["TIME_PROVIDER"]())
    window_start = now - (now % window)
    connection = get_db()
    row = connection.execute(
        """
        INSERT INTO rate_limits (client_key, endpoint, window_start, request_count)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(client_key, endpoint, window_start)
        DO UPDATE SET request_count = request_count + 1
        RETURNING request_count
        """,
        (client_key(), endpoint, window_start),
    ).fetchone()
    connection.commit()

    remaining = max(0, limit - row["request_count"])
    reset = window_start + window
    if row["request_count"] > limit:
        response, status = json_error(
            "Rate limit exceeded", 429, retry_after=max(1, reset - now)
        )
        response.headers["Retry-After"] = str(max(1, reset - now))
    else:
        response, status = None, None

    if response is not None:
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset)
        return response, status
    return None


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=str(Path(app.instance_path) / "shortener.sqlite"),
        CODE_LENGTH=8,
        CODE_ATTEMPTS=10,
        RATE_LIMIT=10,
        RATE_LIMIT_WINDOW=60,
        TIME_PROVIDER=time.time,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    @app.post("/api/shorten")
    def shorten():
        limited = enforce_rate_limit("shorten")
        if limited:
            return limited

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or "url" not in payload:
            return json_error("A JSON body with a 'url' field is required", 400)
        target_url = payload["url"]
        if not valid_url(target_url):
            return json_error("URL must be a valid HTTP or HTTPS URL", 422)

        connection = get_db()
        created_at = utc_timestamp(current_app.config["TIME_PROVIDER"]())
        code = None
        for _ in range(current_app.config["CODE_ATTEMPTS"]):
            candidate = generate_code(current_app.config["CODE_LENGTH"])
            try:
                connection.execute(
                    "INSERT INTO urls (code, target_url, created_at) VALUES (?, ?, ?)",
                    (candidate, target_url, created_at),
                )
                connection.commit()
                code = candidate
                break
            except sqlite3.IntegrityError:
                connection.rollback()
        if code is None:
            current_app.logger.error("Could not allocate a unique short code")
            return json_error("Unable to create a short URL", 503)

        return (
            jsonify(
                {
                    "code": code,
                    "short_url": url_for("follow", code=code, _external=True),
                    "url": target_url,
                    "created_at": created_at,
                }
            ),
            201,
        )

    @app.get("/<code>")
    def follow(code):
        connection = get_db()
        row = connection.execute(
            "SELECT target_url FROM urls WHERE code = ?", (code,)
        ).fetchone()
        if row is None:
            return json_error("Short URL not found", 404)

        now = utc_timestamp(current_app.config["TIME_PROVIDER"]())
        connection.execute(
            """
            INSERT INTO clicks (code, clicked_at, referrer, user_agent)
            VALUES (?, ?, ?, ?)
            """,
            (
                code,
                now,
                request.referrer,
                request.user_agent.string[:512] or None,
            ),
        )
        connection.execute(
            "UPDATE urls SET click_count = click_count + 1 WHERE code = ?", (code,)
        )
        connection.commit()
        return redirect(row["target_url"], code=302)

    @app.get("/api/urls/<code>/stats")
    def stats(code):
        connection = get_db()
        url_row = connection.execute(
            """
            SELECT code, target_url, created_at, click_count
            FROM urls WHERE code = ?
            """,
            (code,),
        ).fetchone()
        if url_row is None:
            return json_error("Short URL not found", 404)

        recent = connection.execute(
            """
            SELECT clicked_at, referrer, user_agent
            FROM clicks WHERE code = ? ORDER BY id DESC LIMIT 20
            """,
            (code,),
        ).fetchall()
        return jsonify(
            {
                "code": url_row["code"],
                "url": url_row["target_url"],
                "created_at": url_row["created_at"],
                "click_count": url_row["click_count"],
                "recent_clicks": [dict(click) for click in recent],
            }
        )

    @app.errorhandler(404)
    def not_found(_error):
        return json_error("Not found", 404)

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return json_error("Method not allowed", 405)

    return app
