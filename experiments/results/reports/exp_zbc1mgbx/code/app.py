"""URL Shortener — counterpoint codegen, polyrhythm rate limiting, overtone analytics, diminuendo sizing."""

import hashlib
import hmac
import json
import os
import re
import sqlite3
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlparse

from flask import Flask, Response, g, jsonify, redirect, request

# ---------------------------------------------------------------------------
# App & config
# ---------------------------------------------------------------------------

app = Flask(__name__)

BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
SECRET = os.environ.get("SHORTENER_SECRET", os.urandom(32).hex())
DATABASE = os.environ.get("SHORTENER_DB", ":memory:")
DOMAIN = os.environ.get("SHORTENER_DOMAIN", "http://localhost:5000")

# diminuendo — start short; grow only when collisions force it
MIN_CODE_LEN = 4
MAX_CODE_LEN = 10

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS urls (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT    NOT NULL UNIQUE,
            url         TEXT    NOT NULL,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_urls_code ON urls(code);

        CREATE TABLE IF NOT EXISTS clicks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT    NOT NULL,
            timestamp   TEXT    NOT NULL DEFAULT (datetime('now')),
            ip          TEXT,
            user_agent  TEXT,
            referrer    TEXT,
            FOREIGN KEY (code) REFERENCES urls(code)
        );
        CREATE INDEX IF NOT EXISTS idx_clicks_code ON clicks(code);
        CREATE INDEX IF NOT EXISTS idx_clicks_ts   ON clicks(timestamp);
    """)
    db.commit()
    db.close()


with app.app_context():
    init_db()

# ---------------------------------------------------------------------------
# Code generation — counterpoint of hash-based + counter-based fallback
# ---------------------------------------------------------------------------

def _base62_encode(n: int) -> str:
    if n == 0:
        return BASE62[0]
    chars = []
    while n > 0:
        chars.append(BASE62[n % 62])
        n //= 62
    return "".join(reversed(chars))


def _code_exists(code: str) -> bool:
    db = get_db()
    row = db.execute("SELECT 1 FROM urls WHERE code = ?", (code,)).fetchone()
    return row is not None


def generate_code(url: str, length: int = MIN_CODE_LEN) -> str:
    """Counterpoint: primary = HMAC-based hash; fallback = monotonically-incrementing counter."""
    # Primary voice — hash-derived (unpredictable, no enumeration)
    entropy = f"{url}|{time.time_ns()}|{os.urandom(8).hex()}"
    digest = hmac.new(SECRET.encode(), entropy.encode(), hashlib.sha256).hexdigest()
    primary = _base62_encode(int(digest, 16))[:length]

    if not _code_exists(primary):
        return primary

    # Secondary voice — counter-based for guaranteed collision avoidance
    for attempt_len in range(length, MAX_CODE_LEN + 1):
        counter_val = int(datetime.now(timezone.utc).timestamp() * 1_000_000)
        for _ in range(100):
            counter_val += 1
            fallback = _base62_encode(counter_val)[-attempt_len:]
            if not _code_exists(fallback):
                return fallback

    # Last resort: full-width random
    for _ in range(200):
        candidate = _base62_encode(int.from_bytes(os.urandom(8), "big"))[:MAX_CODE_LEN]
        if not _code_exists(candidate):
            return candidate

    raise RuntimeError("Code generation exhausted — key space saturated")


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _normalise_url(raw: str) -> str | None:
    raw = raw.strip()
    if not re.match(r"^https?://", raw):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if not parsed.netloc:
        return None
    scheme = parsed.scheme or "https"
    return f"{scheme}://{parsed.netloc}{parsed.path}{'?' + parsed.query if parsed.query else ''}"


@app.errorhandler(400)
def bad_request(_e):
    return jsonify({"error": "bad request"}), 400


@app.errorhandler(429)
def rate_limited(_e):
    return jsonify({"error": "rate limit exceeded"}), 429


# ---------------------------------------------------------------------------
# Rate limiting — polyrhythm (three independent time-scales)
# ---------------------------------------------------------------------------

class PolyrhythmLimiter:
    """Three concurrent buckets: 10/s, 100/min, 1000/hour per client IP."""

    def __init__(self):
        self._lock = threading.Lock()
        self._buckets: dict[str, dict[str, deque[float]]] = {}

    @staticmethod
    def _now() -> float:
        return time.monotonic()

    def _ensure_bucket(self, ip: str):
        if ip not in self._buckets:
            self._buckets[ip] = {
                "per_sec": deque(),
                "per_min": deque(),
                "per_hour": deque(),
            }

    def check(self, ip: str) -> bool:
        now = self._now()
        with self._lock:
            self._ensure_bucket(ip)
            b = self._buckets[ip]

            # per second — 10 req
            while b["per_sec"] and now - b["per_sec"][0] > 1.0:
                b["per_sec"].popleft()
            if len(b["per_sec"]) >= 10:
                return False

            # per minute — 100 req
            while b["per_min"] and now - b["per_min"][0] > 60.0:
                b["per_min"].popleft()
            if len(b["per_min"]) >= 100:
                return False

            # per hour — 1000 req
            while b["per_hour"] and now - b["per_hour"][0] > 3600.0:
                b["per_hour"].popleft()
            if len(b["per_hour"]) >= 1000:
                return False

            b["per_sec"].append(now)
            b["per_min"].append(now)
            b["per_hour"].append(now)
            return True

    def remaining(self, ip: str) -> dict:
        now = self._now()
        with self._lock:
            self._ensure_bucket(ip)
            b = self._buckets[ip]
            while b["per_sec"] and now - b["per_sec"][0] > 1.0:
                b["per_sec"].popleft()
            while b["per_min"] and now - b["per_min"][0] > 60.0:
                b["per_min"].popleft()
            while b["per_hour"] and now - b["per_hour"][0] > 3600.0:
                b["per_hour"].popleft()
            return {
                "per_second": max(0, 10 - len(b["per_sec"])),
                "per_minute": max(0, 100 - len(b["per_min"])),
                "per_hour": max(0, 1000 - len(b["per_hour"])),
            }


limiter = PolyrhythmLimiter()


def rate_limit(f):
    @wraps(f)
    def wrapper(*a, **kw):
        ip = request.remote_addr or "127.0.0.1"
        if not limiter.check(ip):
            return jsonify({"error": "rate limit exceeded"}), 429
        return f(*a, **kw)

    return wrapper


# ---------------------------------------------------------------------------
# API — REST endpoints
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "url-shortener",
        "endpoints": {
            "POST /api/shorten": "Create short URL (body: {url: ...})",
            "GET /api/stats/<code>": "Click analytics",
            "GET /api/limit": "Check rate-limit status",
        },
    })


@app.route("/api/shorten", methods=["POST"])
@rate_limit
def shorten():
    body = request.get_json(silent=True)
    if not body or "url" not in body:
        return jsonify({"error": "missing 'url' in JSON body"}), 400

    raw_url = str(body["url"]).strip()
    if len(raw_url) > 2048:
        return jsonify({"error": "URL too long"}), 400

    normalised = _normalise_url(raw_url)
    if normalised is None:
        return jsonify({"error": "invalid URL"}), 400

    db = get_db()

    # Reuse existing
    existing = db.execute("SELECT code FROM urls WHERE url = ?", (normalised,)).fetchone()
    if existing:
        return jsonify({"short_url": f"{DOMAIN}/{existing['code']}", "code": existing["code"]}), 200

    # Generate new
    code = generate_code(normalised)
    db.execute("INSERT INTO urls (code, url) VALUES (?, ?)", (code, normalised))
    db.commit()

    return jsonify({"short_url": f"{DOMAIN}/{code}", "code": code}), 201


@app.route("/<code>", methods=["GET"])
def redirect_to(code: str):
    if not re.fullmatch(rf"[{re.escape(BASE62)}]+", code) or len(code) > MAX_CODE_LEN:
        return jsonify({"error": "not found"}), 404

    db = get_db()
    row = db.execute("SELECT url FROM urls WHERE code = ?", (code,)).fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404

    # Log click
    db.execute(
        "INSERT INTO clicks (code, ip, user_agent, referrer) VALUES (?, ?, ?, ?)",
        (
            code,
            request.remote_addr,
            request.headers.get("User-Agent", "")[:512],
            request.headers.get("Referer", "")[:2048],
        ),
    )
    db.commit()

    return redirect(row["url"], code=302)


@app.route("/api/stats/<code>", methods=["GET"])
def stats(code: str):
    if not re.fullmatch(rf"[{re.escape(BASE62)}]+", code) or len(code) > MAX_CODE_LEN:
        return jsonify({"error": "not found"}), 404

    db = get_db()
    url_row = db.execute("SELECT * FROM urls WHERE code = ?", (code,)).fetchone()
    if not url_row:
        return jsonify({"error": "not found"}), 404

    # Total clicks
    total = db.execute("SELECT COUNT(*) as c FROM clicks WHERE code = ?", (code,)).fetchone()["c"]

    # Overtone — hourly heatmap (last 7 days)
    hourly = db.execute("""
        SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
        FROM clicks
        WHERE code = ? AND timestamp >= datetime('now', '-7 days')
        GROUP BY 1 ORDER BY 1
    """, (code,)).fetchall()

    # Top referrers
    referrers = db.execute("""
        SELECT referrer, COUNT(*) as count
        FROM clicks
        WHERE code = ? AND referrer IS NOT NULL AND referrer != ''
        GROUP BY 1 ORDER BY 2 DESC LIMIT 10
    """, (code,)).fetchall()

    # Last 20 clicks
    recent = db.execute("""
        SELECT timestamp, ip, user_agent, referrer
        FROM clicks
        WHERE code = ?
        ORDER BY timestamp DESC LIMIT 20
    """, (code,)).fetchall()

    # Build overtone heatmap (0-23 hours)
    heatmap = {h: 0 for h in range(24)}
    for row in hourly:
        heatmap[int(row["hour"])] = row["count"]

    # Find peak overtone
    if total > 0:
        peak_hour = max(heatmap, key=heatmap.get)
        peak_desc = f"hour {peak_hour:02d}:00"
    else:
        peak_desc = "n/a"

    return jsonify({
        "code": code,
        "original_url": url_row["url"],
        "created_at": url_row["created_at"],
        "total_clicks": total,
        "peak_overtone": peak_desc,
        "hourly_heatmap": heatmap,
        "top_referrers": [{"referrer": r["referrer"], "count": r["count"]} for r in referrers],
        "recent_clicks": [dict(r) for r in recent],
    })


@app.route("/api/limit", methods=["GET"])
def limit_status():
    ip = request.remote_addr or "127.0.0.1"
    return jsonify({"ip": ip, "remaining": limiter.remaining(ip)}), 200


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
