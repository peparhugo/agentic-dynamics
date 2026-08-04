import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import Blueprint, request, jsonify, redirect, current_app

from db import insert_url, get_url_by_code, insert_click, get_clicks, get_click_stats, code_exists
from shortener import generate_unique_code
from rate_limit import limit_shorten, get_shorten_remaining

api = Blueprint("api", __name__)

URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)
MAX_URL_LENGTH = 2048


def _validate_url(url):
    if not url or not isinstance(url, str):
        return "URL is required"
    if len(url) > MAX_URL_LENGTH:
        return f"URL exceeds maximum length of {MAX_URL_LENGTH}"
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "URL must start with http:// or https://"
    if not parsed.netloc:
        return "Invalid URL"
    if not URL_RE.match(url):
        return "Invalid URL format"
    return None


@api.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})


@api.route("/shorten", methods=["POST"])
def shorten():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    if not limit_shorten(ip):
        return jsonify({
            "error": "rate_limit_exceeded",
            "retry_after_seconds": 60,
            "remaining": 0,
        }), 429

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    url = data.get("url", "").strip()
    err = _validate_url(url)
    if err:
        return jsonify({"error": err}), 400

    custom_code = data.get("custom_code", "").strip() or None
    db_path = current_app.config["DB_PATH"]

    if custom_code:
        if len(custom_code) < 3 or len(custom_code) > 30:
            return jsonify({"error": "custom_code must be between 3 and 30 characters"}), 400
        if not re.match(r"^[a-zA-Z0-9_-]+$", custom_code):
            return jsonify({"error": "custom_code can only contain letters, numbers, hyphens, and underscores"}), 400
        if code_exists(db_path, custom_code):
            return jsonify({"error": "custom_code already taken"}), 409
        code = custom_code
    else:
        try:
            code = generate_unique_code(db_path)
        except RuntimeError:
            return jsonify({"error": "Could not generate unique code, please try again"}), 503

    record = insert_url(db_path, code, url)
    host = request.host_url.rstrip("/")
    return jsonify({
        "short_url": f"{host}/{code}",
        "code": code,
        "long_url": record["url"],
        "created_at": record["created_at"],
    }), 201


@api.route("/<code>/stats", methods=["GET"])
def stats(code):
    db_path = current_app.config["DB_PATH"]
    url_record = get_url_by_code(db_path, code)
    if url_record is None:
        return jsonify({"error": "not_found"}), 404
    s = get_click_stats(db_path, code)
    return jsonify({
        "code": code,
        "long_url": url_record["url"],
        "created_at": url_record["created_at"],
        **s,
    })


@api.route("/<code>/clicks", methods=["GET"])
def clicks(code):
    db_path = current_app.config["DB_PATH"]
    url_record = get_url_by_code(db_path, code)
    if url_record is None:
        return jsonify({"error": "not_found"}), 404

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)
    if page < 1:
        page = 1

    offset = (page - 1) * per_page
    rows = get_clicks(db_path, code, limit=per_page, offset=offset)

    return jsonify({
        "code": code,
        "long_url": url_record["url"],
        "page": page,
        "per_page": per_page,
        "clicks": rows,
    })


@api.route("/<code>", methods=["GET"])
def redirect_to_url(code):
    db_path = current_app.config["DB_PATH"]
    url_record = get_url_by_code(db_path, code)
    if url_record is None:
        return jsonify({"error": "not_found"}), 404

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    user_agent = request.headers.get("User-Agent", "")[:512]
    referer = request.headers.get("Referer", "")[:2048]
    insert_click(db_path, code, ip, user_agent, referer)

    return redirect(url_record["url"], code=302)
