import sqlite3
import secrets
import string
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from functools import wraps

from flask import Flask, request, jsonify, redirect, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
app.config["DATABASE"] = "shortener.db"

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

ALPHABET = string.ascii_letters + string.digits  # base62, 62 chars
CODE_LENGTH = 7
MAX_GENERATION_ATTEMPTS = 5


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(app.config["DATABASE"])
    db.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT UNIQUE NOT NULL,
            original_url TEXT NOT NULL,
            created_at TEXT NOT NULL,
            click_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            referrer TEXT,
            FOREIGN KEY (short_code) REFERENCES urls(short_code)
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_urls_code ON urls(short_code)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_clicks_code ON clicks(short_code)")
    db.commit()
    db.close()


def generate_code():
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def is_valid_url(url):
    try:
        parsed = urlparse(url)
        return all([parsed.scheme in ("http", "https"), parsed.netloc])
    except Exception:
        return False


@app.route("/")
def index():
    return jsonify({
        "service": "URL Shortener API",
        "endpoints": {
            "POST /api/shorten": "Shorten a URL. Body: {\"url\": \"...\"}",
            "GET /<code>": "Redirect to original URL",
            "GET /api/stats/<code>": "Get click analytics for a short code",
            "GET /api/urls": "List all shortened URLs",
        }
    })


@app.route("/api/shorten", methods=["POST"])
@limiter.limit("10 per minute")
def shorten_url():
    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return jsonify({"error": "Missing 'url' in request body"}), 400

    original_url = data["url"].strip()
    if not is_valid_url(original_url):
        return jsonify({"error": "Invalid URL"}), 400

    db = get_db()

    existing = db.execute(
        "SELECT short_code FROM urls WHERE original_url = ?", (original_url,)
    ).fetchone()
    if existing:
        return jsonify({
            "short_code": existing["short_code"],
            "short_url": f"{request.host_url}{existing['short_code']}",
            "original_url": original_url,
        }), 200

    for _ in range(MAX_GENERATION_ATTEMPTS):
        code = generate_code()
        try:
            db.execute(
                "INSERT INTO urls (short_code, original_url, created_at) VALUES (?, ?, ?)",
                (code, original_url, datetime.now(timezone.utc).isoformat()),
            )
            db.commit()
            return jsonify({
                "short_code": code,
                "short_url": f"{request.host_url}{code}",
                "original_url": original_url,
            }), 201
        except sqlite3.IntegrityError:
            continue

    return jsonify({"error": "Could not generate unique code. Try again."}), 500


@app.route("/<code>")
def redirect_to_url(code):
    db = get_db()
    row = db.execute(
        "SELECT original_url, short_code FROM urls WHERE short_code = ?", (code,)
    ).fetchone()

    if not row:
        return jsonify({"error": "Short URL not found"}), 404

    db.execute(
        "INSERT INTO clicks (short_code, timestamp, ip_address, user_agent, referrer) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            code,
            datetime.now(timezone.utc).isoformat(),
            request.remote_addr,
            request.headers.get("User-Agent", ""),
            request.headers.get("Referer", ""),
        ),
    )
    db.execute(
        "UPDATE urls SET click_count = click_count + 1 WHERE short_code = ?", (code,)
    )
    db.commit()

    return redirect(row["original_url"], code=302)


@app.route("/api/stats/<code>")
@limiter.limit("5 per minute")
def get_stats(code):
    db = get_db()
    url_row = db.execute(
        "SELECT * FROM urls WHERE short_code = ?", (code,)
    ).fetchone()

    if not url_row:
        return jsonify({"error": "Short URL not found"}), 404

    click_rows = db.execute(
        "SELECT * FROM clicks WHERE short_code = ? ORDER BY timestamp DESC LIMIT 100",
        (code,),
    ).fetchall()

    return jsonify({
        "short_code": url_row["short_code"],
        "original_url": url_row["original_url"],
        "created_at": url_row["created_at"],
        "total_clicks": url_row["click_count"],
        "recent_clicks": [
            {
                "timestamp": c["timestamp"],
                "ip_address": c["ip_address"],
                "user_agent": c["user_agent"],
                "referrer": c["referrer"],
            }
            for c in click_rows
        ],
    }), 200


@app.route("/api/urls")
@limiter.limit("5 per minute")
def list_urls():
    db = get_db()
    rows = db.execute(
        "SELECT short_code, original_url, created_at, click_count "
        "FROM urls ORDER BY created_at DESC LIMIT 100"
    ).fetchall()
    return jsonify([
        {
            "short_code": r["short_code"],
            "short_url": f"{request.host_url}{r['short_code']}",
            "original_url": r["original_url"],
            "created_at": r["created_at"],
            "click_count": r["click_count"],
        }
        for r in rows
    ]), 200


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
