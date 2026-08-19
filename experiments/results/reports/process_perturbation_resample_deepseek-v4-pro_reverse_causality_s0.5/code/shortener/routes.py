"""REST API routes for the URL shortener."""

from urllib.parse import urlparse

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    request,
    url_for,
)

from .shortcodes import generate_unique_short_code

bp = Blueprint("shortener", __name__)


def _validate_url(raw: str) -> str:
    """Return a normalized URL, or raise ValueError."""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("url is required")
    url = raw.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("url must be an absolute http(s) URL")
    return url


def _client_ip() -> str:
    # Respect common reverse-proxy headers in production; fall back to remote.
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()


def _rate_limited() -> bool:
    limiter = current_app.extensions["rate_limiter"]
    return limiter.allow(_client_ip())


@bp.post("/api/shorten")
def shorten():
    if not _rate_limited():
        return jsonify(error="rate limit exceeded"), 429

    data = request.get_json(silent=True) or {}
    try:
        original_url = _validate_url(data.get("url"))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    db = current_app.extensions["db"]
    length = current_app.config["SHORT_CODE_LENGTH"]
    attempts = current_app.config["MAX_CODE_ATTEMPTS"]

    try:
        short_code = generate_unique_short_code(
            db.code_exists, length=length, max_attempts=attempts
        )
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 503

    # Defensive double-check against the (vanishingly unlikely) race where the
    # code is inserted between check and insert; retry once on collision.
    if not db.insert_url(short_code, original_url):
        try:
            short_code = generate_unique_short_code(
                db.code_exists, length=length, max_attempts=attempts
            )
        except RuntimeError as exc:
            return jsonify(error=str(exc)), 503
        if not db.insert_url(short_code, original_url):
            return jsonify(error="could not allocate short code"), 503

    short_url = url_for("shortener.redirect_to_url", short_code=short_code,
                        _external=True)
    return jsonify(
        short_code=short_code,
        short_url=short_url,
        original_url=original_url,
    ), 201


@bp.get("/api/<short_code>")
def resolve(short_code):
    db = current_app.extensions["db"]
    row = db.get_url(short_code)
    if row is None:
        return jsonify(error="not found"), 404
    return jsonify(
        short_code=row["short_code"],
        original_url=row["original_url"],
        created_at=row["created_at"],
    )


@bp.get("/api/<short_code>/stats")
def stats(short_code):
    db = current_app.extensions["db"]
    row = db.get_url(short_code)
    if row is None:
        return jsonify(error="not found"), 404
    return jsonify(
        short_code=row["short_code"],
        original_url=row["original_url"],
        created_at=row["created_at"],
        clicks=db.click_count(short_code),
        recent=db.recent_clicks(short_code),
    )


@bp.get("/<short_code>")
def redirect_to_url(short_code):
    if not _rate_limited():
        return jsonify(error="rate limit exceeded"), 429

    db = current_app.extensions["db"]
    row = db.get_url(short_code)
    if row is None:
        return jsonify(error="not found"), 404

    db.record_click(
        short_code,
        ip=_client_ip(),
        user_agent=request.headers.get("User-Agent"),
    )
    return redirect(row["original_url"], code=302)
