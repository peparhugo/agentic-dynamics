import secrets
import sqlite3
import string
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, current_app, g, jsonify, redirect, request, url_for


ALPHABET = string.ascii_letters + string.digits


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def generate_code(length: int) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA busy_timeout = 10000")
    return g.db


def close_db(_error: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db() -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    connection = sqlite3.connect(current_app.config["DATABASE"])
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(schema_path.read_text(encoding="utf-8"))
    finally:
        connection.close()


def valid_url(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 4096:
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except ValueError:
        return False


def error(message: str, status: int, **headers: str):
    response = jsonify({"error": message})
    response.status_code = status
    response.headers.update(headers)
    return response


def check_rate_limit(scope: str):
    limit = current_app.config["RATE_LIMIT"]
    window = current_app.config["RATE_LIMIT_WINDOW"]
    if limit <= 0:
        return None

    now = int(time.time())
    window_start = now - (now % window)
    client = request.remote_addr or "unknown"
    db = get_db()
    with db:
        row = db.execute(
            """
            INSERT INTO rate_limits (client, scope, window_start, requests)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(client, scope, window_start)
            DO UPDATE SET requests = requests + 1
            RETURNING requests
            """,
            (client, scope, window_start),
        ).fetchone()

    if row["requests"] > limit:
        retry_after = window_start + window - now
        return error(
            "rate limit exceeded",
            429,
            **{"Retry-After": str(retry_after), "X-RateLimit-Limit": str(limit)},
        )
    return None


def serialize_url(row: sqlite3.Row) -> dict:
    return {
        "code": row["code"],
        "url": row["url"],
        "short_url": url_for("follow_url", code=row["code"], _external=True),
        "created_at": row["created_at"],
        "clicks": row["clicks"],
    }


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=str(Path(app.instance_path) / "shortener.sqlite3"),
        CODE_LENGTH=8,
        CODE_ATTEMPTS=10,
        RATE_LIMIT=10,
        RATE_LIMIT_WINDOW=60,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    @app.post("/api/urls")
    def create_url():
        limited = check_rate_limit("create_url")
        if limited is not None:
            return limited

        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not valid_url(data.get("url")):
            return error("a valid http or https URL is required", 400)

        db = get_db()
        created_at = utc_now()
        for _ in range(current_app.config["CODE_ATTEMPTS"]):
            code = generate_code(current_app.config["CODE_LENGTH"])
            try:
                with db:
                    db.execute(
                        "INSERT INTO urls (code, url, created_at) VALUES (?, ?, ?)",
                        (code, data["url"], created_at),
                    )
            except sqlite3.IntegrityError:
                continue
            row = db.execute(
                "SELECT code, url, created_at, 0 AS clicks FROM urls WHERE code = ?",
                (code,),
            ).fetchone()
            return jsonify(serialize_url(row)), 201

        return error("could not allocate a unique short code", 503)

    @app.get("/api/urls/<code>")
    def get_url(code: str):
        row = get_db().execute(
            """
            SELECT u.code, u.url, u.created_at, COUNT(c.id) AS clicks
            FROM urls u LEFT JOIN clicks c ON c.code = u.code
            WHERE u.code = ? GROUP BY u.code
            """,
            (code,),
        ).fetchone()
        if row is None:
            return error("short URL not found", 404)
        return jsonify(serialize_url(row))

    @app.delete("/api/urls/<code>")
    def delete_url(code: str):
        db = get_db()
        with db:
            cursor = db.execute("DELETE FROM urls WHERE code = ?", (code,))
        if cursor.rowcount == 0:
            return error("short URL not found", 404)
        return "", 204

    @app.get("/api/urls/<code>/analytics")
    def analytics(code: str):
        try:
            limit = min(max(int(request.args.get("limit", 50)), 1), 100)
        except ValueError:
            return error("limit must be an integer", 400)

        db = get_db()
        url_row = db.execute(
            "SELECT code, url, created_at FROM urls WHERE code = ?", (code,)
        ).fetchone()
        if url_row is None:
            return error("short URL not found", 404)
        click_rows = db.execute(
            """
            SELECT clicked_at, referrer, user_agent, ip_address
            FROM clicks WHERE code = ? ORDER BY id DESC LIMIT ?
            """,
            (code, limit),
        ).fetchall()
        total = db.execute(
            "SELECT COUNT(*) FROM clicks WHERE code = ?", (code,)
        ).fetchone()[0]
        return jsonify(
            {
                "code": code,
                "url": url_row["url"],
                "created_at": url_row["created_at"],
                "total_clicks": total,
                "recent_clicks": [dict(row) for row in click_rows],
            }
        )

    @app.get("/<code>")
    def follow_url(code: str):
        db = get_db()
        row = db.execute("SELECT url FROM urls WHERE code = ?", (code,)).fetchone()
        if row is None:
            return error("short URL not found", 404)
        with db:
            db.execute(
                """
                INSERT INTO clicks (code, clicked_at, referrer, user_agent, ip_address)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    code,
                    utc_now(),
                    request.referrer,
                    request.user_agent.string or None,
                    request.remote_addr,
                ),
            )
        return redirect(row["url"], code=302)

    return app
