from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import Lock
from time import time
from urllib.parse import urlsplit

from flask import Flask, current_app, g, jsonify, redirect, request, url_for


CODE_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
RESERVED_CODES = {"api", "health"}
UTC = timezone.utc


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class SlidingWindowLimiter:
    def __init__(self, limit: int, window: int) -> None:
        self.limit = limit
        self.window = window
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, now: float | None = None) -> tuple[bool, int, int]:
        current = time() if now is None else now
        with self._lock:
            entries = self._requests[key]
            cutoff = current - self.window
            while entries and entries[0] <= cutoff:
                entries.popleft()
            if len(entries) >= self.limit:
                retry_after = max(1, int(entries[0] + self.window - current + 0.999))
                return False, 0, retry_after
            entries.append(current)
            return True, self.limit - len(entries), 0


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db = sqlite3.connect(current_app.config["DATABASE"], timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 5000")
        g.db = db
    return g.db


def close_db(_error: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    db.executescript(
        """
        PRAGMA journal_mode = WAL;
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            target_url TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
        );
        CREATE TABLE IF NOT EXISTS clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_id INTEGER NOT NULL REFERENCES urls(id) ON DELETE CASCADE,
            clicked_at TEXT NOT NULL,
            referrer TEXT,
            user_agent TEXT,
            ip_hash TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_clicks_url_time
            ON clicks(url_id, clicked_at);
        """
    )
    db.commit()


def json_error(status: int, code: str, message: str):
    return jsonify({"error": {"code": code, "message": message}}), status


def valid_url(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 4096:
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and not parsed.username
    except ValueError:
        return False


def parse_expiry(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("expires_at must be an ISO 8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("expires_at must be an ISO 8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError("expires_at must include a timezone")
    parsed = parsed.astimezone(UTC)
    if parsed <= datetime.now(UTC):
        raise ValueError("expires_at must be in the future")
    return parsed.isoformat(timespec="seconds")


def row_payload(row: sqlite3.Row) -> dict[str, object]:
    return {
        "code": row["code"],
        "url": row["target_url"],
        "short_url": url_for("follow", code=row["code"], _external=True),
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "active": bool(row["is_active"]),
    }


def usable(row: sqlite3.Row) -> bool:
    if not row["is_active"]:
        return False
    return row["expires_at"] is None or row["expires_at"] > utc_now()


def client_key() -> str:
    # Only trust Flask's resolved remote address unless a proxy is explicitly configured.
    return request.remote_addr or "unknown"


def create_app(test_config: dict[str, object] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE="shortener.sqlite3",
        CODE_LENGTH=8,
        CODE_ATTEMPTS=10,
        RATE_LIMIT=60,
        RATE_WINDOW_SECONDS=60,
        IP_HASH_SALT="change-me",
    )
    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    limiter = SlidingWindowLimiter(
        int(app.config["RATE_LIMIT"]), int(app.config["RATE_WINDOW_SECONDS"])
    )

    @app.before_request
    def enforce_rate_limit():
        allowed, remaining, retry_after = limiter.check(client_key())
        g.rate_remaining = remaining
        if not allowed:
            response, status = json_error(429, "rate_limit_exceeded", "Too many requests")
            response.status_code = status
            response.headers["Retry-After"] = str(retry_after)
            return response
        return None

    @app.after_request
    def rate_limit_headers(response):
        response.headers["X-RateLimit-Limit"] = str(app.config["RATE_LIMIT"])
        response.headers["X-RateLimit-Remaining"] = str(getattr(g, "rate_remaining", 0))
        return response

    @app.get("/health")
    def health():
        get_db().execute("SELECT 1").fetchone()
        return jsonify({"status": "ok"})

    @app.post("/api/v1/urls")
    def create_url():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return json_error(400, "invalid_json", "A JSON object is required")
        target = data.get("url")
        if not valid_url(target):
            return json_error(422, "invalid_url", "url must be a valid HTTP or HTTPS URL")
        custom = data.get("custom_code")
        if custom is not None and (
            not isinstance(custom, str)
            or not CODE_RE.fullmatch(custom)
            or custom.lower() in RESERVED_CODES
        ):
            return json_error(422, "invalid_code", "custom_code must be 3-64 URL-safe characters")
        try:
            expires_at = parse_expiry(data.get("expires_at"))
        except ValueError as error:
            return json_error(422, "invalid_expiry", str(error))

        db = get_db()
        attempts = 1 if custom else int(app.config["CODE_ATTEMPTS"])
        for _ in range(attempts):
            code = custom or secrets.token_urlsafe(int(app.config["CODE_LENGTH"]))[: int(app.config["CODE_LENGTH"])]
            try:
                cursor = db.execute(
                    "INSERT INTO urls(code, target_url, created_at, expires_at) VALUES (?, ?, ?, ?)",
                    (code, target, utc_now(), expires_at),
                )
                db.commit()
                row = db.execute("SELECT * FROM urls WHERE id = ?", (cursor.lastrowid,)).fetchone()
                response = jsonify(row_payload(row))
                response.status_code = 201
                response.headers["Location"] = url_for("get_url", code=code, _external=True)
                return response
            except sqlite3.IntegrityError:
                db.rollback()
                if custom:
                    return json_error(409, "code_conflict", "custom_code is already in use")
        return json_error(503, "code_generation_failed", "Could not allocate a unique code")

    @app.get("/api/v1/urls")
    def list_urls():
        try:
            limit = min(max(int(request.args.get("limit", 20)), 1), 100)
            offset = max(int(request.args.get("offset", 0)), 0)
        except ValueError:
            return json_error(400, "invalid_pagination", "limit and offset must be integers")
        db = get_db()
        total = db.execute("SELECT COUNT(*) FROM urls").fetchone()[0]
        rows = db.execute(
            "SELECT * FROM urls ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
        return jsonify({"items": [row_payload(row) for row in rows], "total": total, "limit": limit, "offset": offset})

    @app.get("/api/v1/urls/<code>")
    def get_url(code: str):
        row = get_db().execute("SELECT * FROM urls WHERE code = ?", (code,)).fetchone()
        if row is None:
            return json_error(404, "not_found", "Short URL not found")
        return jsonify(row_payload(row))

    @app.patch("/api/v1/urls/<code>")
    def update_url(code: str):
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not data:
            return json_error(400, "invalid_json", "A non-empty JSON object is required")
        allowed = {"url", "expires_at", "active"}
        if set(data) - allowed:
            return json_error(422, "unknown_field", "Only url, expires_at, and active may be changed")
        db = get_db()
        row = db.execute("SELECT * FROM urls WHERE code = ?", (code,)).fetchone()
        if row is None:
            return json_error(404, "not_found", "Short URL not found")
        target = data.get("url", row["target_url"])
        if not valid_url(target):
            return json_error(422, "invalid_url", "url must be a valid HTTP or HTTPS URL")
        try:
            expires_at = parse_expiry(data["expires_at"]) if "expires_at" in data else row["expires_at"]
        except ValueError as error:
            return json_error(422, "invalid_expiry", str(error))
        active = data.get("active", bool(row["is_active"]))
        if not isinstance(active, bool):
            return json_error(422, "invalid_active", "active must be a boolean")
        db.execute(
            "UPDATE urls SET target_url = ?, expires_at = ?, is_active = ? WHERE id = ?",
            (target, expires_at, int(active), row["id"]),
        )
        db.commit()
        updated = db.execute("SELECT * FROM urls WHERE id = ?", (row["id"],)).fetchone()
        return jsonify(row_payload(updated))

    @app.delete("/api/v1/urls/<code>")
    def delete_url(code: str):
        db = get_db()
        cursor = db.execute("DELETE FROM urls WHERE code = ?", (code,))
        db.commit()
        if cursor.rowcount == 0:
            return json_error(404, "not_found", "Short URL not found")
        return "", 204

    @app.get("/api/v1/urls/<code>/analytics")
    def analytics(code: str):
        db = get_db()
        row = db.execute("SELECT * FROM urls WHERE code = ?", (code,)).fetchone()
        if row is None:
            return json_error(404, "not_found", "Short URL not found")
        summary = db.execute(
            "SELECT COUNT(*) AS total, MIN(clicked_at) AS first_click, MAX(clicked_at) AS last_click FROM clicks WHERE url_id = ?",
            (row["id"],),
        ).fetchone()
        daily = db.execute(
            "SELECT substr(clicked_at, 1, 10) AS date, COUNT(*) AS clicks FROM clicks WHERE url_id = ? GROUP BY date ORDER BY date",
            (row["id"],),
        ).fetchall()
        referrers = db.execute(
            "SELECT COALESCE(NULLIF(referrer, ''), 'direct') AS referrer, COUNT(*) AS clicks FROM clicks WHERE url_id = ? GROUP BY COALESCE(NULLIF(referrer, ''), 'direct') ORDER BY clicks DESC, referrer LIMIT 10",
            (row["id"],),
        ).fetchall()
        return jsonify({
            "code": code,
            "total_clicks": summary["total"],
            "first_click": summary["first_click"],
            "last_click": summary["last_click"],
            "clicks_by_day": [dict(item) for item in daily],
            "top_referrers": [dict(item) for item in referrers],
        })

    @app.get("/<code>")
    def follow(code: str):
        db = get_db()
        row = db.execute("SELECT * FROM urls WHERE code = ?", (code,)).fetchone()
        if row is None:
            return json_error(404, "not_found", "Short URL not found")
        if not usable(row):
            return json_error(410, "gone", "Short URL is inactive or expired")
        address = client_key()
        ip_hash = hashlib.sha256(f"{app.config['IP_HASH_SALT']}:{address}".encode()).hexdigest()
        db.execute(
            "INSERT INTO clicks(url_id, clicked_at, referrer, user_agent, ip_hash) VALUES (?, ?, ?, ?, ?)",
            (row["id"], utc_now(), request.referrer, request.user_agent.string[:512], ip_hash),
        )
        db.commit()
        return redirect(row["target_url"], code=302)

    @app.errorhandler(404)
    def route_not_found(_error):
        return json_error(404, "not_found", "Route not found")

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return json_error(405, "method_not_allowed", "Method not allowed")

    return app
