import math
import secrets
import sqlite3
import time
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, current_app, g, jsonify, redirect, request


SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    code TEXT PRIMARY KEY,
    destination TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    click_count INTEGER NOT NULL DEFAULT 0,
    last_clicked_at INTEGER
);

CREATE TABLE IF NOT EXISTS clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL REFERENCES urls(code) ON DELETE CASCADE,
    clicked_at INTEGER NOT NULL,
    referrer TEXT,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS clicks_code_time ON clicks(code, clicked_at DESC);

CREATE TABLE IF NOT EXISTS rate_limits (
    scope TEXT NOT NULL,
    client_key TEXT NOT NULL,
    window_start INTEGER NOT NULL,
    request_count INTEGER NOT NULL,
    PRIMARY KEY (scope, client_key, window_start)
);
"""


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=str(Path(app.instance_path) / "shortener.sqlite3"),
        BASE_URL=None,
        CODE_BYTES=9,
        CODE_GENERATION_ATTEMPTS=10,
        MAX_URL_LENGTH=2048,
        CREATE_RATE_LIMIT=10,
        READ_RATE_LIMIT=120,
        REDIRECT_RATE_LIMIT=120,
        RATE_LIMIT_WINDOW=60,
        TIME_PROVIDER=time.time,
    )
    if config:
        app.config.update(config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.executescript(SCHEMA)

    app.teardown_appcontext(close_database)

    @app.post("/api/urls")
    @rate_limited("create", "CREATE_RATE_LIMIT")
    def create_short_url():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not isinstance(data.get("url"), str):
            return error("A JSON object containing a string 'url' is required", 400)

        destination = data["url"].strip()
        validation_error = validate_destination(destination)
        if validation_error:
            return error(validation_error, 400)

        now = current_time()
        connection = get_database()
        for _ in range(current_app.config["CODE_GENERATION_ATTEMPTS"]):
            code = generate_code()
            try:
                connection.execute(
                    "INSERT INTO urls (code, destination, created_at) VALUES (?, ?, ?)",
                    (code, destination, now),
                )
                connection.commit()
                payload = serialize_url(code, destination, now, 0, None)
                return jsonify(payload), 201, {"Location": payload["short_url"]}
            except sqlite3.IntegrityError:
                connection.rollback()

        return error("Could not allocate a unique short code", 503)

    @app.get("/api/urls/<code>")
    @rate_limited("read", "READ_RATE_LIMIT")
    def get_url_analytics(code):
        row = get_database().execute(
            """SELECT code, destination, created_at, click_count, last_clicked_at
               FROM urls WHERE code = ?""",
            (code,),
        ).fetchone()
        if row is None:
            return error("Short URL not found", 404)

        payload = serialize_url(*row)
        payload["recent_clicks"] = [
            {
                "clicked_at": click[0],
                "referrer": click[1],
                "user_agent": click[2],
            }
            for click in get_database().execute(
                """SELECT clicked_at, referrer, user_agent FROM clicks
                   WHERE code = ? ORDER BY clicked_at DESC, id DESC LIMIT 20""",
                (code,),
            )
        ]
        return jsonify(payload)

    @app.get("/<code>")
    @rate_limited("redirect", "REDIRECT_RATE_LIMIT")
    def follow_short_url(code):
        connection = get_database()
        row = connection.execute(
            "SELECT destination FROM urls WHERE code = ?", (code,)
        ).fetchone()
        if row is None:
            return error("Short URL not found", 404)

        now = current_time()
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                """INSERT INTO clicks (code, clicked_at, referrer, user_agent)
                   VALUES (?, ?, ?, ?)""",
                (
                    code,
                    now,
                    limited_header("Referer", 2048),
                    limited_header("User-Agent", 512),
                ),
            )
            connection.execute(
                """UPDATE urls SET click_count = click_count + 1,
                   last_clicked_at = ? WHERE code = ?""",
                (now, code),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return redirect(row[0], code=302)

    @app.get("/health")
    def health():
        get_database().execute("SELECT 1").fetchone()
        return jsonify({"status": "ok"})

    return app


def get_database():
    if "database" not in g:
        g.database = sqlite3.connect(
            current_app.config["DATABASE"], timeout=5, isolation_level=None
        )
        g.database.execute("PRAGMA foreign_keys = ON")
        g.database.execute("PRAGMA busy_timeout = 5000")
    return g.database


def close_database(_exception=None):
    connection = g.pop("database", None)
    if connection is not None:
        connection.close()


def current_time():
    return int(current_app.config["TIME_PROVIDER"]())


def generate_code():
    return secrets.token_urlsafe(current_app.config["CODE_BYTES"])


def validate_destination(destination):
    if not destination:
        return "URL must not be empty"
    if len(destination) > current_app.config["MAX_URL_LENGTH"]:
        return "URL is too long"
    try:
        parsed = urlsplit(destination)
        port = parsed.port
    except ValueError:
        return "URL is malformed"
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "Only absolute HTTP and HTTPS URLs are supported"
    if port is not None and not 1 <= port <= 65535:
        return "URL has an invalid port"
    return None


def serialize_url(code, destination, created_at, click_count, last_clicked_at):
    base_url = current_app.config["BASE_URL"] or request.host_url
    return {
        "code": code,
        "url": destination,
        "short_url": f"{base_url.rstrip('/')}/{code}",
        "created_at": created_at,
        "click_count": click_count,
        "last_clicked_at": last_clicked_at,
    }


def rate_limited(scope, limit_config):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            limit = current_app.config[limit_config]
            window = current_app.config["RATE_LIMIT_WINDOW"]
            now = current_time()
            window_start = now - (now % window)
            client_key = request.remote_addr or "unknown"
            connection = get_database()
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """INSERT INTO rate_limits
                       (scope, client_key, window_start, request_count)
                       VALUES (?, ?, ?, 1)
                       ON CONFLICT(scope, client_key, window_start)
                       DO UPDATE SET request_count = request_count + 1""",
                    (scope, client_key, window_start),
                )
                count = connection.execute(
                    """SELECT request_count FROM rate_limits
                       WHERE scope = ? AND client_key = ? AND window_start = ?""",
                    (scope, client_key, window_start),
                ).fetchone()[0]
                connection.commit()
            except Exception:
                connection.rollback()
                raise

            remaining = max(0, limit - count)
            headers = {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(window_start + window),
            }
            if count > limit:
                headers["Retry-After"] = str(max(1, math.ceil(window_start + window - now)))
                response, status = error("Rate limit exceeded", 429)
                response.headers.update(headers)
                return response, status

            response = current_app.make_response(view(*args, **kwargs))
            response.headers.update(headers)
            return response

        return wrapped

    return decorate


def limited_header(name, maximum):
    value = request.headers.get(name)
    return value[:maximum] if value else None


def error(message, status):
    return jsonify({"error": message}), status
