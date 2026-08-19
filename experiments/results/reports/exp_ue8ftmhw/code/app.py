import os
import secrets
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone

from flask import Flask, g, jsonify, redirect, request

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(ALPHABET)
DEFAULT_BASE_URL = "http://localhost:5000"


def code_exists(db_path, code):
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT 1 FROM urls WHERE code = ?", (code,)).fetchone()
    finally:
        conn.close()
    return row is not None


def new_code(db_path, length=6, max_retries=20):
    attempts = 0
    while True:
        code = encode_base62(secrets.randbelow(BASE ** length), length)
        if not code_exists(db_path, code):
            return code
        attempts += 1
        if attempts > max_retries:
            length += 1


def encode_base62(num, length):
    out = []
    for _ in range(length):
        out.append(ALPHABET[num % BASE])
        num //= BASE
    return "".join(reversed(out))


class RateLimiter:
    """Fixed-window per-IP rate limiter with in-memory storage."""

    def __init__(self, limit, window):
        self.limit = limit
        self.window = window
        self.hits = {}

    def allow(self, key):
        now = time.time()
        bucket = int(now // self.window)
        entry = self.hits.get(key)
        if entry is None or entry[0] != bucket:
            self.hits[key] = (bucket, 1)
            return True, self.limit - 1
        count = entry[1]
        if count >= self.limit:
            return False, 0
        self.hits[key] = (bucket, count + 1)
        return True, self.limit - count - 1

    def reset(self):
        self.hits.clear()


def get_db(db_path):
    conn = getattr(g, "_db", None)
    if conn is None:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        g._db = conn
    return conn


def close_db(_exc=None):
    conn = getattr(g, "_db", None)
    if conn is not None:
        conn.close()
        g._db = None


def init_db(db_path):
    conn = sqlite3.connect(db_path)
    with closing(conn) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS urls (
                code       TEXT PRIMARY KEY,
                url        TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS clicks (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                code       TEXT NOT NULL REFERENCES urls(code),
                ip         TEXT,
                user_agent TEXT,
                referrer   TEXT,
                clicked_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_clicks_code ON clicks(code);
            """
        )
        conn.commit()


def make_app(db_path=None, rate_limit=60, rate_window=60, base_url=None):
    if db_path is None:
        db_path = os.environ.get("URLSHORT_DB", "urlshort.db")
    if base_url is None:
        base_url = os.environ.get("URLSHORT_BASE_URL", DEFAULT_BASE_URL)

    app = Flask(__name__)
    app.config["DB_PATH"] = db_path
    app.config["BASE_URL"] = base_url.rstrip("/")
    app.config["CODE_LENGTH"] = int(os.environ.get("URLSHORT_CODE_LENGTH", "6"))
    app.config["MAX_RETRIES"] = int(os.environ.get("URLSHORT_MAX_RETRIES", "20"))
    limiter = RateLimiter(rate_limit, rate_window)

    init_db(db_path)

    app.teardown_appcontext(close_db)
    app.config["LIMITER"] = limiter

    def client_ip():
        return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()

    def new_code_for_url():
        return new_code(
            app.config["DB_PATH"],
            length=app.config["CODE_LENGTH"],
            max_retries=app.config["MAX_RETRIES"],
        )

    def insert_url(code, url):
        now = time.time()
        get_db(app.config["DB_PATH"]).execute(
            "INSERT INTO urls (code, url, created_at) VALUES (?, ?, ?)",
            (code, url, now),
        )
        get_db(app.config["DB_PATH"]).commit()
        return now

    def valid_url(raw):
        url = raw.strip()
        if not url:
            return None
        if "://" not in url:
            url = "http://" + url
        if len(url) > 2048 or any(c.isspace() for c in url):
            return None
        return url

    @app.route("/api/shorten", methods=["POST"])
    def shorten():
        limiter = app.config["LIMITER"]
        allowed, remaining = limiter.allow(client_ip())
        if not allowed:
            return jsonify(error="rate limit exceeded"), 429
        payload = request.get_json(silent=True) or request.form
        if not payload:
            return jsonify(error="missing body"), 400
        url = valid_url(payload.get("url", ""))
        if url is None:
            return jsonify(error="invalid url"), 400
        code = new_code_for_url()
        insert_url(code, url)
        short_url = f"{app.config['BASE_URL']}/{code}"
        return jsonify(code=code, url=url, short_url=short_url), 201

    @app.route("/api/stats/<code>")
    def stats(code):
        db = get_db(app.config["DB_PATH"])
        row = db.execute("SELECT code, url, created_at FROM urls WHERE code = ?", (code,)).fetchone()
        if row is None:
            return jsonify(error="not found"), 404
        total = db.execute("SELECT COUNT(*) AS n FROM clicks WHERE code = ?", (code,)).fetchone()["n"]
        by_day = db.execute(
            "SELECT date(clicked_at, 'unixepoch') AS day, COUNT(*) AS n "
            "FROM clicks WHERE code = ? GROUP BY day ORDER BY day",
            (code,),
        ).fetchall()
        referrers = db.execute(
            "SELECT COALESCE(NULLIF(referrer,''), '(direct)') AS ref, COUNT(*) AS n "
            "FROM clicks WHERE code = ? GROUP BY ref ORDER BY n DESC LIMIT 10",
            (code,),
        ).fetchall()
        agents = db.execute(
            "SELECT COALESCE(NULLIF(user_agent,''), '(unknown)') AS ua, COUNT(*) AS n "
            "FROM clicks WHERE code = ? GROUP BY ua ORDER BY n DESC LIMIT 10",
            (code,),
        ).fetchall()
        return jsonify(
            code=row["code"],
            url=row["url"],
            created_at=datetime.fromtimestamp(row["created_at"], timezone.utc).isoformat(),
            total_clicks=total,
            clicks_by_day=[{"day": r["day"], "count": r["n"]} for r in by_day],
            top_referrers=[{"referrer": r["ref"], "count": r["n"]} for r in referrers],
            top_user_agents=[{"user_agent": r["ua"], "count": r["n"]} for r in agents],
        )

    @app.route("/<code>")
    def redirect_code(code):
        db = get_db(app.config["DB_PATH"])
        row = db.execute("SELECT code, url FROM urls WHERE code = ?", (code,)).fetchone()
        if row is None:
            return jsonify(error="not found"), 404
        db.execute(
            "INSERT INTO clicks (code, ip, user_agent, referrer, clicked_at) VALUES (?, ?, ?, ?, ?)",
            (
                row["code"],
                client_ip(),
                request.headers.get("User-Agent", ""),
                request.headers.get("Referer", ""),
                time.time(),
            ),
        )
        db.commit()
        return redirect(row["url"], code=302)

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify(error="not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(_e):
        return jsonify(error="method not allowed"), 405

    return app


app = make_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
