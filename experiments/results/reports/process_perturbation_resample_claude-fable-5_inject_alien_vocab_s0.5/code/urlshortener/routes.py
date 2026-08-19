from urllib.parse import urlparse

from flask import Blueprint, current_app, jsonify, redirect, request

from . import limiter
from .models import Click, URL, db
from .shortcode import generate_unique_code

bp = Blueprint("urlshortener", __name__)

CUSTOM_CODE_MIN_LEN = 3
CUSTOM_CODE_MAX_LEN = 32
CUSTOM_CODE_ALLOWED_EXTRA = {"-", "_"}
RESERVED_CODES = {"api", "health"}


def _is_valid_url(url):
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _is_valid_custom_code(code):
    if not (CUSTOM_CODE_MIN_LEN <= len(code) <= CUSTOM_CODE_MAX_LEN):
        return False
    return all(c.isalnum() or c in CUSTOM_CODE_ALLOWED_EXTRA for c in code)


def _code_exists(code):
    return db.session.query(URL.id).filter_by(short_code=code).first() is not None


def _get_or_404(code):
    return URL.query.filter_by(short_code=code).first()


@bp.get("/api/health")
def health():
    return jsonify(status="ok")


@bp.post("/api/urls")
@limiter.limit("20 per minute")
def create_url():
    payload = request.get_json(silent=True) or {}
    long_url = (payload.get("url") or "").strip()
    custom_code = (payload.get("custom_code") or "").strip() or None

    if not long_url:
        return jsonify(error="'url' is required"), 400
    if not _is_valid_url(long_url):
        return jsonify(error="Invalid URL; must be an absolute http(s) URL"), 400

    if custom_code:
        if custom_code.lower() in RESERVED_CODES or not _is_valid_custom_code(custom_code):
            return (
                jsonify(
                    error=(
                        "custom_code must be 3-32 characters of letters, "
                        "digits, '-' or '_' and not a reserved word"
                    )
                ),
                400,
            )
        if _code_exists(custom_code):
            return jsonify(error="custom_code already taken"), 409
        code = custom_code
    else:
        code = generate_unique_code(
            _code_exists, length=current_app.config["SHORT_CODE_LENGTH"]
        )

    url = URL(short_code=code, long_url=long_url)
    db.session.add(url)
    db.session.commit()

    return jsonify(url.to_dict(base_url=current_app.config["BASE_URL"])), 201


@bp.get("/api/urls/<code>")
def get_url(code):
    url = _get_or_404(code)
    if not url:
        return jsonify(error="short code not found"), 404
    return jsonify(url.to_dict(base_url=current_app.config["BASE_URL"]))


@bp.get("/api/urls/<code>/analytics")
def analytics(code):
    url = _get_or_404(code)
    if not url:
        return jsonify(error="short code not found"), 404

    clicks = (
        Click.query.filter_by(url_id=url.id).order_by(Click.timestamp.desc()).all()
    )
    return jsonify(
        short_code=url.short_code,
        long_url=url.long_url,
        click_count=len(clicks),
        clicks=[
            {
                "timestamp": c.timestamp.isoformat(),
                "ip_address": c.ip_address,
                "user_agent": c.user_agent,
                "referrer": c.referrer,
            }
            for c in clicks
        ],
    )


@bp.delete("/api/urls/<code>")
def delete_url(code):
    url = _get_or_404(code)
    if not url:
        return jsonify(error="short code not found"), 404
    db.session.delete(url)
    db.session.commit()
    return "", 204


@bp.get("/<code>")
@limiter.limit("60 per minute")
def redirect_short_code(code):
    url = _get_or_404(code)
    if not url:
        return jsonify(error="short code not found"), 404

    click = Click(
        url_id=url.id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", ""),
        referrer=request.headers.get("Referer", ""),
    )
    db.session.add(click)
    db.session.commit()

    return redirect(url.long_url, code=302)
