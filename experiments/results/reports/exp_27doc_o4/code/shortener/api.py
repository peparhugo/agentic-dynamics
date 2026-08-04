"""REST API and redirect routes."""

from __future__ import annotations

from urllib.parse import urlparse

from flask import Blueprint, current_app, jsonify, request, redirect, url_for

from .shortcode import generate_code, is_valid_custom_code
from .storage import CodeCollisionError, ShortUrl, SQLiteStorage
from .ratelimit import RateLimiter

bp = Blueprint("shortener", __name__)

MAX_URL_LENGTH = 2048
MAX_CODE_RETRIES = 5


def _storage() -> SQLiteStorage:
    return current_app.extensions["storage"]


def _limiter() -> RateLimiter:
    return current_app.extensions["rate_limiter"]


def _client_key() -> str:
    # Honour the first X-Forwarded-For hop when behind a trusted proxy.
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _error(status: int, message: str, **extra):
    payload = {"error": message, **extra}
    return jsonify(payload), status


def _serialize(entry: ShortUrl) -> dict:
    return {
        "code": entry.code,
        "short_url": url_for("shortener.follow", code=entry.code, _external=True),
        "long_url": entry.long_url,
        "created_at": entry.created_at,
        "clicks": entry.clicks,
    }


def _validate_url(raw: str) -> str | None:
    """Return a normalized URL or None if invalid."""
    if not raw or len(raw) > MAX_URL_LENGTH:
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return raw


@bp.before_request
def enforce_rate_limit():
    # Rate-limit only the API surface; redirects stay fast and unmetered.
    if not request.path.startswith("/api/"):
        return None
    allowed, retry_after = _limiter().allow(_client_key())
    if not allowed:
        resp, status = _error(429, "rate limit exceeded", retry_after=round(retry_after, 2))
        resp.headers["Retry-After"] = str(max(int(retry_after) + 1, 1))
        return resp, status
    return None


@bp.post("/api/shorten")
def shorten():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error(400, "request body must be a JSON object")

    long_url = _validate_url(str(data.get("url", "")).strip())
    if long_url is None:
        return _error(400, "'url' must be a valid http(s) URL (max 2048 chars)")

    custom = data.get("custom_code")
    storage = _storage()

    if custom is not None:
        custom = str(custom)
        if not is_valid_custom_code(custom):
            return _error(
                400,
                "'custom_code' must be 4-32 chars of [0-9a-zA-Z_-]",
            )
        try:
            entry = storage.save(custom, long_url)
        except CodeCollisionError:
            return _error(409, f"code '{custom}' is already taken")
        return jsonify(_serialize(entry)), 201

    # Idempotent shorten: reuse an existing random mapping for the same URL.
    existing = storage.find_by_url(long_url)
    if existing is not None:
        return jsonify(_serialize(existing)), 200

    length = current_app.config["CODE_LENGTH"]
    for _ in range(MAX_CODE_RETRIES):
        try:
            entry = storage.save(generate_code(length), long_url)
            return jsonify(_serialize(entry)), 201
        except CodeCollisionError:
            continue
    return _error(500, "could not allocate a unique code, try again")


@bp.get("/api/urls/<code>")
def stats(code: str):
    entry = _storage().get(code)
    if entry is None:
        return _error(404, "unknown code")
    return jsonify(_serialize(entry))


@bp.delete("/api/urls/<code>")
def remove(code: str):
    if not _storage().delete(code):
        return _error(404, "unknown code")
    return "", 204


@bp.get("/<code>")
def follow(code: str):
    entry = _storage().get(code)
    if entry is None:
        return _error(404, "unknown code")
    _storage().increment_clicks(code)
    return redirect(entry.long_url, code=302)


@bp.get("/api/health")
def health():
    return jsonify({"status": "ok"})
