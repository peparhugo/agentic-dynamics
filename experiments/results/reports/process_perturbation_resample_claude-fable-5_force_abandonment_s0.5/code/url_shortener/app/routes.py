from urllib.parse import urlparse

from flask import Blueprint, current_app, jsonify, redirect, request

from .analytics import build_summary
from .db import get_db
from .ratelimit import rate_limited
from .repository import ClickRepository, LinkRepository

bp = Blueprint("shortener", __name__)


def _repos():
    db = get_db()
    code_length = current_app.config["CODE_LENGTH"]
    return LinkRepository(db, code_length=code_length), ClickRepository(db)


def _is_valid_url(url):
    if not isinstance(url, str) or len(url) > 4096:
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


@bp.post("/api/shorten")
@rate_limited("shorten")
def shorten():
    payload = request.get_json(silent=True) or {}
    url = payload.get("url")

    if not _is_valid_url(url):
        return jsonify({"error": "url must be a valid http(s) URL"}), 400

    link_repo, _ = _repos()
    link, created = link_repo.get_or_create(url)
    status = 201 if created else 200
    return jsonify(link.to_dict(current_app.config["BASE_URL"])), status


@bp.get("/api/links/<code>")
@rate_limited("read")
def get_link(code):
    link_repo, click_repo = _repos()
    link = link_repo.find_by_code(code)
    if link is None:
        return jsonify({"error": "not found"}), 404
    data = link.to_dict(current_app.config["BASE_URL"])
    data["clicks"] = click_repo.count_for(code)
    return jsonify(data)


@bp.get("/api/links/<code>/analytics")
@rate_limited("read")
def get_analytics(code):
    link_repo, click_repo = _repos()
    link = link_repo.find_by_code(code)
    if link is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(build_summary(link, click_repo))


@bp.delete("/api/links/<code>")
@rate_limited("write")
def delete_link(code):
    link_repo, _ = _repos()
    deleted = link_repo.delete(code)
    if not deleted:
        return jsonify({"error": "not found"}), 404
    return "", 204


@bp.get("/<code>")
@rate_limited("redirect")
def follow(code):
    link_repo, click_repo = _repos()
    link = link_repo.find_by_code(code)
    if link is None:
        return jsonify({"error": "not found"}), 404

    click_repo.record(
        code,
        referrer=request.headers.get("Referer"),
        ip=request.headers.get("X-Forwarded-For", request.remote_addr),
    )
    return redirect(link.url, code=302)
