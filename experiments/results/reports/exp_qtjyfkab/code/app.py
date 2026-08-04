import hashlib
import os
import sqlite3
import time
from datetime import datetime, timezone
from functools import wraps
from threading import Lock

from flask import Flask, g, jsonify, redirect, request

app = Flask(__name__)
app.config["DATABASE"] = os.environ.get("DB_PATH", "urls.db")
app.config["CODE_LENGTH"] = 7
app.config["RATE_LIMIT_REQUESTS"] = 10
app.config["RATE_LIMIT_WINDOW"] = 60

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
BASE = len(ALPHABET)


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
    return db


def init_db():
    db = sqlite3.connect(app.config["DATABASE"])
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            original_url TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_code TEXT NOT NULL,
            clicked_at TEXT NOT NULL,
            ip TEXT,
            user_agent TEXT,
            referer TEXT,
            FOREIGN KEY (url_code) REFERENCES urls(code)
        );
        CREATE INDEX IF NOT EXISTS idx_clicks_url_code ON clicks(url_code);
        CREATE INDEX IF NOT EXISTS idx_urls_code ON urls(code);
        """
    )
    db.commit()
    db.close()


@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def encode_base62(num: int) -> str:
    if num == 0:
        return ALPHABET[0]
    chars = []
    while num > 0:
        num, rem = divmod(num, BASE)
        chars.append(ALPHABET[rem])
    return "".join(reversed(chars))


def generate_code(url: str) -> str:
    digest = hashlib.sha256(
        f"{url}{time.time_ns()}{os.urandom(16).hex()}".encode()
    ).digest()
    num = int.from_bytes(digest, "big")
    return encode_base62(num)[: app.config["CODE_LENGTH"]]


def create_code(url: str) -> str:
    db = get_db()
    for _ in range(5):
        code = generate_code(url)
        try:
            db.execute(
                "INSERT INTO urls (code, original_url, created_at) VALUES (?, ?, ?)",
                (code, url, datetime.now(timezone.utc).isoformat()),
            )
            db.commit()
            return code
        except sqlite3.IntegrityError:
            continue
    raise RuntimeError("Failed to generate unique code after 5 attempts")


_rate_limit_store: dict[str, list[float]] = {}
_rate_lock = Lock()


def rate_limit(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        ip = request.remote_addr or "127.0.0.1"
        now = time.time()
        window = app.config["RATE_LIMIT_WINDOW"]
        max_reqs = app.config["RATE_LIMIT_REQUESTS"]

        with _rate_lock:
            timestamps = _rate_limit_store.get(ip, [])
            timestamps = [t for t in timestamps if now - t < window]
            if len(timestamps) >= max_reqs:
                return (
                    jsonify({"error": "Rate limit exceeded. Try again later."}),
                    429,
                )
            timestamps.append(now)
            _rate_limit_store[ip] = timestamps

        return f(*args, **kwargs)

    return wrapper


@app.route("/shorten", methods=["POST"])
@rate_limit
def shorten():
    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return jsonify({"error": "Missing 'url' field in JSON body"}), 400

    url = data["url"].strip()
    if not url:
        return jsonify({"error": "URL must not be empty"}), 400

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    code = create_code(url)
    return jsonify({"short_url": f"{request.host_url}{code}", "code": code}), 201


@app.route("/<code>", methods=["GET"])
def redirect_to_url(code):
    db = get_db()
    row = db.execute(
        "SELECT code, original_url, is_active FROM urls WHERE code = ?", (code,)
    ).fetchone()

    if not row:
        return jsonify({"error": "Short URL not found"}), 404

    if not row["is_active"]:
        return jsonify({"error": "Short URL has been deactivated"}), 410

    db.execute(
        "INSERT INTO clicks (url_code, clicked_at, ip, user_agent, referer) VALUES (?, ?, ?, ?, ?)",
        (
            code,
            datetime.now(timezone.utc).isoformat(),
            request.remote_addr,
            request.headers.get("User-Agent", ""),
            request.headers.get("Referer", ""),
        ),
    )
    db.commit()

    return redirect(row["original_url"], 302)


@app.route("/<code>/stats", methods=["GET"])
def get_stats(code):
    db = get_db()
    url_row = db.execute(
        "SELECT code, original_url, created_at, is_active FROM urls WHERE code = ?",
        (code,),
    ).fetchone()

    if not url_row:
        return jsonify({"error": "Short URL not found"}), 404

    total_clicks = db.execute(
        "SELECT COUNT(*) as count FROM clicks WHERE url_code = ?", (code,)
    ).fetchone()["count"]

    unique_ips = db.execute(
        "SELECT COUNT(DISTINCT ip) as count FROM clicks WHERE url_code = ?", (code,)
    ).fetchone()["count"]

    last_click = db.execute(
        "SELECT clicked_at FROM clicks WHERE url_code = ? ORDER BY clicked_at DESC LIMIT 1",
        (code,),
    ).fetchone()

    daily_clicks = db.execute(
        """
        SELECT DATE(clicked_at) as day, COUNT(*) as count
        FROM clicks WHERE url_code = ?
        GROUP BY DATE(clicked_at)
        ORDER BY day DESC
        LIMIT 30
        """,
        (code,),
    ).fetchall()

    top_referers = db.execute(
        """
        SELECT referer, COUNT(*) as count
        FROM clicks WHERE url_code = ? AND referer != ''
        GROUP BY referer
        ORDER BY count DESC
        LIMIT 10
        """,
        (code,),
    ).fetchall()

    return jsonify(
        {
            "code": url_row["code"],
            "original_url": url_row["original_url"],
            "created_at": url_row["created_at"],
            "is_active": bool(url_row["is_active"]),
            "total_clicks": total_clicks,
            "unique_ips": unique_ips,
            "last_clicked_at": last_click["clicked_at"] if last_click else None,
            "daily_clicks": [dict(row) for row in daily_clicks],
            "top_referers": [dict(row) for row in top_referers],
        }
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
