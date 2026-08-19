"""Collision-resistant URL shortener with REST API, persistence, rate limiting,
and click analytics."""

import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from flask import Flask, jsonify, redirect, request

# 62-character URL-safe alphabet (unambiguous base62)
ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
DEFAULT_CODE_LENGTH = 7

# Custom code rules
CUSTOM_CODE_RE = re.compile(r"^[a-zA-Z0-9_-]{4,32}$")
RESERVED_CODES = {"api", "stats", "health", "robots.txt", "favicon.ico"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    code        TEXT PRIMARY KEY,
    original    TEXT NOT NULL,
    created_at  REAL NOT NULL,
    clicks      INTEGER NOT NULL DEFAULT 0,
    last_click  REAL
);

CREATE TABLE IF NOT EXISTS clicks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL,
    clicked_at  REAL NOT NULL,
    ip          TEXT,
    user_agent  TEXT,
    referrer    TEXT
);
CREATE INDEX IF NOT EXISTS idx_clicks_code ON clicks (code);
"""


def _validate_url(url):
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


class URLStore:
    """Thread-safe SQLite-backed storage."""

    def __init__(self, db_path):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def create(self, code, original):
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO urls (code, original, created_at) VALUES (?, ?, ?)",
                    (code, original, time.time()),
                )
                self._conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get(self, code):
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM urls WHERE code = ?", (code,)
            ).fetchone()
        return dict(row) if row else None

    def record_click(self, code, ip, user_agent, referrer):
        with self._lock:
            self._conn.execute(
                "INSERT INTO clicks (code, clicked_at, ip, user_agent, referrer) "
                "VALUES (?, ?, ?, ?, ?)",
                (code, time.time(), ip, user_agent, referrer),
            )
            self._conn.execute(
                "UPDATE urls SET clicks = clicks + 1, last_click = ? WHERE code = ?",
                (time.time(), code),
            )
            self._conn.commit()

    def stats(self, code):
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM urls WHERE code = ?", (code,)
            ).fetchone()
            if row is None:
                return None
            data = dict(row)
            data["recent_clicks"] = [
                dict(c)
                for c in self._conn.execute(
                    "SELECT clicked_at, ip, user_agent, referrer FROM clicks "
                    "WHERE code = ? ORDER BY clicked_at DESC LIMIT 50",
                    (code,),
                ).fetchall()
            ]
            return data


class SlidingWindowLimiter:
    """Sliding-window rate limiter keyed by client identity."""

    def __init__(self, max_requests, window_seconds):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._hits = defaultdict(deque)

    def allow(self, key):
        now = time.monotonic()
        with self._lock:
            dq = self._hits[key]
            while dq and dq[0] <= now - self.window_seconds:
                dq.popleft()
            if len(dq) >= self.max_requests:
                return False
            dq.append(now)
            return True


class Shortener:
    def __init__(self, store, code_length=DEFAULT_CODE_LENGTH):
        self.store = store
        self.code_length = code_length

    def _random_code(self):
        return "".join(secrets.choice(ALPHABET) for _ in range(self.code_length))

    def shorten(self, original, custom_code=None):
        original = (original or "").strip()
        if not _validate_url(original):
            raise ValueError("invalid URL")

        if custom_code is not None:
            custom_code = custom_code.strip()
            if not CUSTOM_CODE_RE.match(custom_code):
                raise ValueError("custom code must be 4-32 chars of [a-zA-Z0-9_-]")
            if custom_code.lower() in RESERVED_CODES:
                raise ValueError("custom code is reserved")
            if not self.store.create(custom_code, original):
                raise KeyError("custom code already in use")
            return custom_code

        for _ in range(100):
            code = self._random_code()
            if code.lower() in RESERVED_CODES:
                continue
            if self.store.create(code, original):
                return code
        raise RuntimeError("unable to generate a unique code")


def create_app(db_path=":memory:", config=None):
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    cfg = {
        "RATE_LIMIT_MAX": 60,
        "RATE_LIMIT_WINDOW": 60,
        "CODE_LENGTH": DEFAULT_CODE_LENGTH,
    }
    if config:
        cfg.update(config)

    store = URLStore(db_path)
    limiter = SlidingWindowLimiter(cfg["RATE_LIMIT_MAX"], cfg["RATE_LIMIT_WINDOW"])
    shortener = Shortener(store, cfg["CODE_LENGTH"])

    app.extensions["store"] = store
    app.extensions["limiter"] = limiter
    app.extensions["shortener"] = shortener

    def client_ip():
        return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")

    @app.errorhandler(429)
    def ratelimited(e):
        return jsonify(error="rate limit exceeded"), 429

    @app.route("/health")
    def health():
        return jsonify(status="ok")

    @app.route("/api/shorten", methods=["POST"])
    def shorten():
        if not limiter.allow(client_ip()):
            return jsonify(error="rate limit exceeded"), 429

        payload = request.get_json(silent=True) or {}
        original = payload.get("url")
        custom_code = payload.get("custom_code")

        try:
            code = shortener.shorten(original, custom_code)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except KeyError as exc:
            return jsonify(error=str(exc)), 409

        entry = store.get(code)
        return (
            jsonify(
                {
                    "short_code": code,
                    "short_url": f"{request.url_root}{code}",
                    "original_url": entry["original"],
                    "created_at": entry["created_at"],
                }
            ),
            201,
        )

    @app.route("/api/<code>")
    def lookup(code):
        entry = store.get(code)
        if entry is None:
            return jsonify(error="not found"), 404
        return jsonify(
            {
                "short_code": code,
                "original_url": entry["original"],
                "clicks": entry["clicks"],
                "created_at": entry["created_at"],
            }
        )

    @app.route("/api/<code>/stats")
    def stats(code):
        data = store.stats(code)
        if data is None:
            return jsonify(error="not found"), 404
        return jsonify(
            {
                "short_code": code,
                "original_url": data["original"],
                "clicks": data["clicks"],
                "created_at": data["created_at"],
                "last_click": data["last_click"],
                "recent_clicks": data["recent_clicks"],
            }
        )

    @app.route("/<code>")
    def redirect_to(code):
        entry = store.get(code)
        if entry is None:
            return jsonify(error="not found"), 404
        store.record_click(
            code, client_ip(), request.headers.get("User-Agent"), request.referrer
        )
        return redirect(entry["original"], code=302)

    return app


if __name__ == "__main__":
    create_app("urls.db").run(debug=True)
