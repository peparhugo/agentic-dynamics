import hashlib
import os
import sqlite3
import time
import threading
from flask import Flask, jsonify, redirect, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = False

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per hour"],
    storage_uri="memory://",
)

DB_PATH = os.environ.get("SHORTENER_DB", ":memory:")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


_lock = threading.Lock()


def _init_db():
    with _conn() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS urls (
                short_code TEXT PRIMARY KEY,
                long_url TEXT NOT NULL,
                created_at REAL NOT NULL,
                hits INTEGER NOT NULL DEFAULT 0
            )"""
        )


_init_db()


def _generate_code(length: int = 6) -> str:
    raw = os.urandom(9)
    digest = hashlib.sha256(raw).digest()
    b64 = (
        __import__("base64")
        .urlsafe_b64encode(digest[:length])
        .decode("ascii")
        .rstrip("=")
    )
    return b64[:length]


def _insert(short_code: str, long_url: str) -> bool:
    with _lock:
        with _conn() as conn:
            try:
                conn.execute(
                    "INSERT INTO urls (short_code, long_url, created_at) VALUES (?, ?, ?)",
                    (short_code, long_url, time.time()),
                )
                return True
            except sqlite3.IntegrityError:
                return False


def _lookup(short_code: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT long_url, created_at, hits FROM urls WHERE short_code = ?",
            (short_code,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)


def _increment_hits(short_code: str) -> None:
    with _lock:
        with _conn() as conn:
            conn.execute(
                "UPDATE urls SET hits = hits + 1 WHERE short_code = ?",
                (short_code,),
            )


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/shorten", methods=["POST"])
@limiter.limit("10 per minute")
def shorten():
    body = request.get_json(silent=True) or {}
    long_url = (body.get("url") or "").strip()
    if not long_url:
        return jsonify({"error": "url is required"}), 400

    if not long_url.startswith(("http://", "https://")):
        long_url = "https://" + long_url

    for _ in range(10):
        code = _generate_code()
        if _insert(code, long_url):
            return jsonify({"short_code": code, "long_url": long_url}), 201

    return jsonify({"error": "could not generate unique code"}), 500


@app.route("/<short_code>")
@limiter.limit("120 per minute")
def redirect_to(short_code):
    row = _lookup(short_code)
    if row is None:
        return jsonify({"error": "not found"}), 404
    _increment_hits(short_code)
    return redirect(row["long_url"], code=302)


@app.route("/<short_code>/stats")
@limiter.limit("30 per minute")
def stats(short_code):
    row = _lookup(short_code)
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(
        {
            "short_code": short_code,
            "long_url": row["long_url"],
            "hits": row["hits"],
            "created_at": row["created_at"],
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
