from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, redirect, request

from codegen import generate_code
from config import Config
from models import ShortURL
from ratelimit import SlidingWindowRateLimiter
from storage import Storage

app = Flask(__name__)
app.config.from_object(Config)

storage = Storage()

global_limiter = SlidingWindowRateLimiter(
    Config.RATE_LIMIT_REQUESTS, Config.RATE_LIMIT_WINDOW_SEC
)
create_limiter = SlidingWindowRateLimiter(
    Config.CREATE_RATE_LIMIT_REQUESTS, Config.CREATE_RATE_LIMIT_WINDOW_SEC
)


def _client_key() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")


def _ttl_days_from_request() -> int:
    try:
        ttl = int(request.args.get("ttl_days", ""))
        if ttl > 0:
            return min(ttl, 365)
    except (ValueError, TypeError):
        pass
    return Config.DEFAULT_TTL_DAYS


@app.route("/api/shorten", methods=["POST"])
def shorten_url():
    data = request.get_json(silent=True) or {}
    original_url = (data.get("url") or "").strip()
    if not original_url:
        return jsonify({"error": "Missing 'url' field"}), 400

    custom_code = (data.get("custom_code") or "").strip() or None

    client = _client_key()
    if not create_limiter.is_allowed(client):
        return jsonify({"error": "Rate limit exceeded. Slow down."}), 429

    if custom_code is not None:
        if storage.exists(custom_code):
            return jsonify({"error": "Custom code already taken"}), 409
        short_code = custom_code
    else:
        for _ in range(5):
            short_code = generate_code(original_url)
            if not storage.exists(short_code):
                break
        else:
            return jsonify({"error": "Could not generate unique code. Try again."}), 500

    now = ShortURL.now_iso()
    ttl_days = _ttl_days_from_request()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=ttl_days)
    ).isoformat()

    entry = ShortURL(
        short_code=short_code,
        original_url=original_url,
        created_at=now,
        expires_at=expires_at,
    )
    storage.insert(entry)

    return jsonify({
        "short_code": short_code,
        "short_url": f"{Config.BASE_URL}/{short_code}",
        "original_url": original_url,
        "expires_at": expires_at,
    }), 201


@app.route("/<short_code>")
def redirect_to_url(short_code: str):
    client = _client_key()
    if not global_limiter.is_allowed(client):
        return jsonify({"error": "Rate limit exceeded. Slow down."}), 429

    entry = storage.get(short_code)
    if entry is None:
        return jsonify({"error": "Not found"}), 404

    if entry.expires_at and entry.expires_at <= ShortURL.now_iso():
        return jsonify({"error": "This link has expired"}), 410

    storage.increment_access(short_code)
    return redirect(entry.original_url, code=302)


@app.route("/api/stats/<short_code>")
def url_stats(short_code: str):
    entry = storage.get(short_code)
    if entry is None:
        return jsonify({"error": "Not found"}), 404

    return jsonify({
        "short_code": entry.short_code,
        "original_url": entry.original_url,
        "created_at": entry.created_at,
        "expires_at": entry.expires_at,
        "access_count": entry.access_count,
    })


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/rate_limit")
def rate_limit_info():
    client = _client_key()
    return jsonify({
        "global_remaining": global_limiter.remaining(client),
        "global_max": Config.RATE_LIMIT_REQUESTS,
        "create_remaining": create_limiter.remaining(client),
        "create_max": Config.CREATE_RATE_LIMIT_REQUESTS,
    })


if __name__ == "__main__":
    app.run(debug=True)
