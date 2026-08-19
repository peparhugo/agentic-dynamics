from functools import wraps
from urllib.parse import urlparse

from flask import Blueprint, current_app, jsonify, redirect, request

from .shortcodes import generate_short_code, is_valid_custom_code, CollisionError

bp = Blueprint("shortener", __name__)


def rate_limited(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        limiter = current_app.rate_limiter
        client_key = request.headers.get("X-Forwarded-For", request.remote_addr)
        allowed, retry_after = limiter.allow(client_key)
        if not allowed:
            response = jsonify(
                {"error": "rate limit exceeded", "retry_after": round(retry_after, 2)}
            )
            response.status_code = 429
            response.headers["Retry-After"] = str(int(retry_after) + 1)
            return response
        return view(*args, **kwargs)

    return wrapper


def _is_valid_url(url):
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


@bp.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@bp.post("/api/shorten")
@rate_limited
def shorten():
    payload = request.get_json(silent=True) or {}
    original_url = payload.get("url")
    custom_code = payload.get("custom_code")

    if not original_url or not _is_valid_url(original_url):
        return jsonify({"error": "a valid absolute http(s) url is required"}), 400

    storage = current_app.storage

    if custom_code:
        if not is_valid_custom_code(custom_code):
            return jsonify({"error": "custom_code must be 3-32 alphanumeric characters"}), 400
        if storage.code_exists(custom_code):
            return jsonify({"error": "custom_code already in use"}), 409
        short_code = custom_code
    else:
        try:
            short_code = generate_short_code(
                storage, length=current_app.config["SHORT_CODE_LENGTH"]
            )
        except CollisionError:
            return jsonify({"error": "could not generate a unique short code, try again"}), 503

    storage.create_url(short_code, original_url)
    record = storage.get_url(short_code)

    return (
        jsonify(
            {
                "short_code": short_code,
                "short_url": request.host_url + short_code,
                "original_url": original_url,
                "created_at": record["created_at"],
            }
        ),
        201,
    )


@bp.get("/api/urls/<short_code>")
def url_info(short_code):
    storage = current_app.storage
    record = storage.get_url(short_code)
    if not record:
        return jsonify({"error": "short code not found"}), 404
    return jsonify(
        {
            "short_code": record["short_code"],
            "original_url": record["original_url"],
            "created_at": record["created_at"],
            "click_count": storage.click_count(short_code),
        }
    )


@bp.get("/api/urls/<short_code>/analytics")
def url_analytics(short_code):
    storage = current_app.storage
    if not storage.code_exists(short_code):
        return jsonify({"error": "short code not found"}), 404
    return jsonify(storage.analytics(short_code))


@bp.delete("/api/urls/<short_code>")
def delete_url(short_code):
    storage = current_app.storage
    deleted = storage.delete_url(short_code)
    if not deleted:
        return jsonify({"error": "short code not found"}), 404
    return "", 204


@bp.get("/<short_code>")
@rate_limited
def follow(short_code):
    storage = current_app.storage
    record = storage.get_url(short_code)
    if not record:
        return jsonify({"error": "short code not found"}), 404

    storage.record_click(
        short_code,
        referrer=request.headers.get("Referer"),
        user_agent=request.headers.get("User-Agent"),
        ip=request.headers.get("X-Forwarded-For", request.remote_addr),
    )
    return redirect(record["original_url"], code=302)
