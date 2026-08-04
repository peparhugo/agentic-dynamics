import os
import sqlite3
import threading
import time
import random
from typing import Optional

from flask import Flask, request, jsonify, redirect, g

# Simple in-process rate limiter (per-IP, token bucket-like)
class SimpleRateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self.lock = threading.Lock()
        self.buckets = {}  # ip -> [window_start, count]

    def allow(self, ip: str) -> bool:
        now = int(time.time())
        with self.lock:
            entry = self.buckets.get(ip)
            if not entry:
                self.buckets[ip] = [now, 1]
                return True
            window_start, count = entry
            if now - window_start >= self.window:
                self.buckets[ip] = [now, 1]
                return True
            if count < self.limit:
                entry[1] = count + 1
                return True
            return False


def get_db_path(database: Optional[str]) -> str:
    if database:
        return database
    return os.environ.get("URL_SHORTENER_DB", "url_shortener.db")


def get_db() -> sqlite3.Connection:
    db = getattr(g, "_db", None)
    if db is None:
        path = get_db_path(getattr(g, "_db_path", None))
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        g._db = conn
        db = conn
    return db


def init_db_if_needed(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS urls (
            code TEXT PRIMARY KEY,
            original_url TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            clicked_at TEXT NOT NULL,
            ip TEXT,
            user_agent TEXT,
            FOREIGN KEY (code) REFERENCES urls(code)
        )
        """
    )
    conn.commit()


def code_exists(conn: sqlite3.Connection, code: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM urls WHERE code = ?", (code,))
    return cur.fetchone() is not None


ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def generate_code(conn: sqlite3.Connection, length: int = 6) -> str:
    # Generate a collision-resistant short code by random base62 and checking DB
    max_attempts = 50
    for _ in range(max_attempts):
        code = ''.join(random.choice(ALPHABET) for _ in range(length))
        if not code_exists(conn, code):
            return code
    # Fallback: use a timestamp-based code (very unlikely to collide in tests)
    ts = int(time.time() * 1000)
    code = base62(ts)[:length]
    return code


def base62(n: int) -> str:
    if n == 0:
        return '0'
    s = []
    base = 62
    while n:
        n, r = divmod(n, base)
        s.append(ALPHABET[r])
    return ''.join(reversed(s))


def insert_url(conn: sqlite3.Connection, code: str, original_url: str) -> None:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO urls (code, original_url, created_at) VALUES (?, ?, ?)",
        (code, original_url, time.strftime('%Y-%m-%d %H:%M:%S')),
    )
    conn.commit()


def fetch_url(conn: sqlite3.Connection, code: str):
    cur = conn.cursor()
    cur.execute("SELECT code, original_url FROM urls WHERE code = ?", (code,))
    row = cur.fetchone()
    return row


def log_click(conn: sqlite3.Connection, code: str, ip: Optional[str], user_agent: Optional[str]) -> None:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO clicks (code, clicked_at, ip, user_agent) VALUES (?, ?, ?, ?)",
        (code, time.strftime('%Y-%m-%d %H:%M:%S'), ip, user_agent),
    )
    conn.commit()


def count_clicks(conn: sqlite3.Connection, code: str) -> int:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM clicks WHERE code = ?", (code,))
    row = cur.fetchone()
    return int(row["c"]) if row else 0


def create_app(database: Optional[str] = None, rate_limit: int = 5, rate_window: int = 60) -> Flask:
    app = Flask(__name__)
    app.config["DATABASE"] = database or get_db_path(None)
    # Rate limit: per IP, configurable
    app.config.setdefault("RATE_LIMIT", rate_limit)
    app.config.setdefault("RATE_WINDOW", rate_window)
    # Initialize the db in a lazy fashion per-request

    @app.before_request
    def before_request():
        # Provide a per-request db path
        g._db_path = app.config["DATABASE"]
        # Initialize DB if needed
        db = get_db()
        init_db_if_needed(db)

    # Simple in-process rate limiter instance per app
    limiter = SimpleRateLimiter(app.config["RATE_LIMIT"], app.config["RATE_WINDOW"])

    @app.route("/shorten", methods=["POST"])
    def shorten():
        ip = request.remote_addr or "0.0.0.0"
        if not limiter.allow(ip):
            return jsonify({"error": "rate_limited"}), 429

        data = request.get_json(force=True) or {}
        original_url = data.get("url") or data.get("original_url")
        if not original_url or not isinstance(original_url, str) or not original_url.startswith(("http://", "https://")):
            return jsonify({"error": "invalid_url"}), 400

        provided_code = data.get("code") if isinstance(data.get("code"), str) else None

        conn = get_db()
        code = None
        if provided_code:
            if code_exists(conn, provided_code):
                return jsonify({"error": "code_exists"}), 409
            code = provided_code
        else:
            code = generate_code(conn, length=6)

        insert_url(conn, code, original_url)
        short_url = request.host_url.rstrip("/") + "/" + code
        return jsonify({"code": code, "short_url": short_url}), 201

    @app.route("/analytics/<code>", methods=["GET"])
    def analytics(code):
        conn = get_db()
        row = fetch_url(conn, code)
        if not row:
            return jsonify({"error": "not_found"}), 404
        total = count_clicks(conn, code)
        return jsonify({"code": code, "original_url": row["original_url"], "clicks": total})

    @app.route("/<code>", methods=["GET"])
    def redirect_code(code):
        conn = get_db()
        url_row = fetch_url(conn, code)
        if not url_row:
            return jsonify({"error": "not_found"}), 404
        # Log the click
        log_click(conn, code, request.remote_addr, request.headers.get("User-Agent"))
        return redirect(url_row["original_url"], code=302)

    return app


def main():
    app = create_app()
    # Run the dev server
    app.run(debug=True, port=5000)


if __name__ == "__main__":
    main()
