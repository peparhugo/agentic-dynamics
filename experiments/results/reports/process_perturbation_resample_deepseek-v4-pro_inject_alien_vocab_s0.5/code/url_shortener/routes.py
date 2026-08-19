from collections import Counter
from urllib.parse import urlparse

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect as flask_redirect,
    request,
    url_for,
)
from sqlalchemy.exc import IntegrityError

from . import limiter
from .models import Click, URL, db
from .utils import generate_code

bp = Blueprint("shortener", __name__)

VALID_SCHEMES = {"http", "https"}


def _validate_url(url):
    parsed = urlparse(url)
    return parsed.scheme in VALID_SCHEMES and bool(parsed.netloc)


def _serialize(entry):
    return {
        "code": entry.code,
        "original_url": entry.original_url,
        "short_url": url_for("shortener.redirect", code=entry.code, _external=True),
        "created_at": entry.created_at.isoformat(),
    }


def _generate_unique_code(length, max_attempts):
    for _ in range(max_attempts):
        code = generate_code(length)
        if URL.query.filter_by(code=code).first() is None:
            return code
    return None


@bp.route("/api/urls", methods=["POST"])
@limiter.limit("5 per minute")
def create_url():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "url is required"}), 400
    if not _validate_url(url):
        return jsonify({"error": "url must be a valid http(s) URL"}), 400

    length = current_app.config.get("CODE_LENGTH", 6)
    max_attempts = current_app.config.get("CODE_MAX_ATTEMPTS", 20)

    entry = URL(code=None, original_url=url)
    for _ in range(max_attempts):
        code = generate_code(length)
        if URL.query.filter_by(code=code).first() is not None:
            continue
        entry.code = code
        db.session.add(entry)
        try:
            db.session.commit()
            break
        except IntegrityError:
            db.session.rollback()
            entry.code = None
    else:
        return jsonify({"error": "could not allocate a unique short code"}), 503

    return jsonify(_serialize(entry)), 201


@bp.route("/api/urls", methods=["GET"])
def list_urls():
    urls = URL.query.order_by(URL.created_at.desc()).all()
    return jsonify({"urls": [_serialize(u) for u in urls]})


@bp.route("/api/urls/<code>", methods=["GET"])
def get_url(code):
    entry = URL.query.filter_by(code=code).first()
    if entry is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(_serialize(entry))


@bp.route("/api/urls/<code>", methods=["DELETE"])
@limiter.limit("5 per minute")
def delete_url(code):
    entry = URL.query.filter_by(code=code).first()
    if entry is None:
        return jsonify({"error": "not found"}), 404
    db.session.delete(entry)
    db.session.commit()
    return jsonify({"deleted": code})


@bp.route("/api/urls/<code>/stats", methods=["GET"])
def url_stats(code):
    entry = URL.query.filter_by(code=code).first()
    if entry is None:
        return jsonify({"error": "not found"}), 404

    clicks = Click.query.filter_by(url_id=entry.id).all()

    daily = Counter()
    referers = Counter()
    ips = set()

    for click in clicks:
        daily[click.clicked_at.date().isoformat()] += 1
        if click.referer:
            referers[click.referer] += 1
        if click.ip_address:
            ips.add(click.ip_address)

    return jsonify(
        {
            "code": entry.code,
            "original_url": entry.original_url,
            "total_clicks": len(clicks),
            "unique_visitors": len(ips),
            "daily": dict(daily),
            "referers": dict(referers),
        }
    )


@bp.route("/<code>", methods=["GET"])
@limiter.limit("200 per minute")
def redirect(code):
    entry = URL.query.filter_by(code=code).first()
    if entry is None:
        return jsonify({"error": "not found"}), 404

    click = Click(
        url_id=entry.id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        referer=request.headers.get("Referer"),
    )
    db.session.add(click)
    db.session.commit()

    return flask_redirect(entry.original_url, code=302)
