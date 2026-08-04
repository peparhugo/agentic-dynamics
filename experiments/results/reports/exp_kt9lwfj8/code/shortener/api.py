"""REST API and redirect routes."""

from __future__ import annotations

import math
from urllib.parse import urlparse

from flask import Blueprint, current_app, jsonify, redirect, request, url_for

from .codes import generate_code, is_valid_custom_code

bp = Blueprint("shortener", __name__)

MAX_URL_LENGTH = 2048
MAX_CODE_ATTEMPTS = 5


def _storage():
    return current_app.extensions["storage"]


def _limiter():
    return current_app.extensions["limiter"]


def _client_key() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown") \
        .split(",")[0].strip()


def _error(status: int, message: str, **extra):
    body = {"error": message, **extra}
    return jsonify(body), status


def _validate_url(raw: str) -> str | None:
    """Return normalized URL, or None if invalid."""
    if not raw or len(raw) > MAX_URL_LENGTH:
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return raw


def _link_json(link) -> dict:
    return {
        "code": link.code,
        "long_url": link.long_url,
        "short_url": url_for("shortener.follow", code=link.code, _external=True),
        "created_at": link.created_at,
        "clicks": link.clicks,
    }


@bp.before_request
def enforce_rate_limit():
    allowed, retry_after = _limiter().check(_client_key())
    if not allowed:
        resp, status = _error(429, "rate limit exceeded")
        resp.headers["Retry-After"] = str(math.ceil(retry_after))
        return resp, status
    return None


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.post("/api/shorten")
def shorten():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error(400, "request body must be a JSON object")

    long_url = _validate_url(data.get("url", ""))
    if long_url is None:
        return _error(400, "invalid or missing 'url' (must be http/https)")

    storage = _storage()
    custom = data.get("custom_code")

    if custom is not None:
        if not isinstance(custom, str) or not is_valid_custom_code(custom):
            return _error(400, "invalid custom_code (3-32 chars: alphanumeric, - or _)")
        if not storage.insert(custom, long_url):
            return _error(409, "custom_code already in use")
        return jsonify(_link_json(storage.get(custom))), 201

    # Idempotent shortening: reuse existing code for the same URL.
    existing = storage.find_by_url(long_url)
    if existing is not None:
        return jsonify(_link_json(existing)), 200

    length = current_app.config["CODE_LENGTH"]
    for _ in range(MAX_CODE_ATTEMPTS):
        code = generate_code(length)
        if storage.insert(code, long_url):
            return jsonify(_link_json(storage.get(code))), 201
    return _error(500, "could not allocate a unique code")


@bp.get("/api/links/<code>")
def stats(code: str):
    link = _storage().get(code)
    if link is None:
        return _error(404, "unknown code")
    return jsonify(_link_json(link))


@bp.delete("/api/links/<code>")
def delete(code: str):
    if not _storage().delete(code):
        return _error(404, "unknown code")
    return "", 204


@bp.get("/<code>")
def follow(code: str):
    link = _storage().get(code)
    if link is None:
        return _error(404, "unknown code")
    _storage().record_click(code)
    return redirect(link.long_url, code=302)
