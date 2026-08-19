from __future__ import annotations

import re
import secrets
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urlsplit

from flask import Blueprint, current_app, jsonify, redirect, request, url_for

from .db import get_db


bp = Blueprint("shortener", __name__)
CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def error(message: str, status: int):
    return jsonify(error=message), status


def valid_url(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 4096:
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname)
    except ValueError:
        return False


def serialize_url(row: sqlite3.Row, include_clicks: bool = False) -> dict:
    result = {
        "code": row["code"],
        "url": row["target_url"],
        "short_url": url_for("shortener.follow", code=row["code"], _external=True),
        "created_at": row["created_at"],
        "click_count": row["click_count"],
        "last_clicked_at": row["last_clicked_at"],
    }
    if include_clicks:
        clicks = get_db().execute(
            """SELECT clicked_at, ip_address, referrer, user_agent
               FROM clicks WHERE code = ? ORDER BY id DESC LIMIT 100""",
            (row["code"],),
        ).fetchall()
        result["recent_clicks"] = [dict(click) for click in clicks]
    return result


@bp.before_app_request
def enforce_rate_limit():
    limit = int(current_app.config["RATE_LIMIT"])
    duration = int(current_app.config["RATE_LIMIT_WINDOW"])
    if limit <= 0 or duration <= 0:
        return None

    client = request.remote_addr or "unknown"
    limiter = current_app.extensions["url_shortener_limiter"]
    allowed, remaining, retry_after = limiter.check(client, limit, duration)
    if not allowed:
        response = jsonify(error="rate limit exceeded")
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = "0"
        return response

    request.environ["shortener.rate_limit"] = (limit, remaining)
    return None


@bp.after_app_request
def add_rate_limit_headers(response):
    values = request.environ.get("shortener.rate_limit")
    if values:
        response.headers["X-RateLimit-Limit"] = str(values[0])
        response.headers["X-RateLimit-Remaining"] = str(values[1])
    return response


@bp.post("/api/urls")
def create_url():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("request body must be a JSON object", 400)

    target_url = data.get("url")
    if not valid_url(target_url):
        return error("url must be a valid http or https URL", 400)

    custom_code = data.get("custom_code")
    if custom_code is not None and (
        not isinstance(custom_code, str) or not CODE_PATTERN.fullmatch(custom_code)
    ):
        return error("custom_code must be 3-64 URL-safe characters", 400)

    db = get_db()
    created_at = utc_now()
    attempts = 1 if custom_code else int(current_app.config["SHORT_CODE_ATTEMPTS"])
    for _ in range(attempts):
        code = custom_code or "".join(
            secrets.choice(ALPHABET) for _ in range(int(current_app.config["SHORT_CODE_LENGTH"]))
        )
        try:
            db.execute(
                "INSERT INTO urls (code, target_url, created_at) VALUES (?, ?, ?)",
                (code, target_url, created_at),
            )
            db.commit()
            row = db.execute("SELECT * FROM urls WHERE code = ?", (code,)).fetchone()
            return jsonify(serialize_url(row)), 201
        except sqlite3.IntegrityError:
            db.rollback()
            if custom_code:
                return error("custom_code is already in use", 409)

    return error("could not allocate a unique short code", 503)


@bp.get("/api/urls/<code>")
def url_analytics(code: str):
    row = get_db().execute("SELECT * FROM urls WHERE code = ?", (code,)).fetchone()
    if row is None:
        return error("short code not found", 404)
    return jsonify(serialize_url(row, include_clicks=True))


@bp.delete("/api/urls/<code>")
def delete_url(code: str):
    cursor = get_db().execute("DELETE FROM urls WHERE code = ?", (code,))
    get_db().commit()
    if cursor.rowcount == 0:
        return error("short code not found", 404)
    return "", 204


@bp.get("/<code>")
def follow(code: str):
    db = get_db()
    row = db.execute("SELECT target_url FROM urls WHERE code = ?", (code,)).fetchone()
    if row is None:
        return error("short code not found", 404)

    clicked_at = utc_now()
    with db:
        db.execute(
            """INSERT INTO clicks
               (code, clicked_at, ip_address, referrer, user_agent)
               VALUES (?, ?, ?, ?, ?)""",
            (
                code,
                clicked_at,
                request.remote_addr,
                request.referrer,
                request.user_agent.string or None,
            ),
        )
        db.execute(
            """UPDATE urls SET click_count = click_count + 1, last_clicked_at = ?
               WHERE code = ?""",
            (clicked_at, code),
        )
    return redirect(row["target_url"], code=302)


@bp.app_errorhandler(404)
def not_found(_exception):
    return error("not found", 404)


@bp.app_errorhandler(405)
def method_not_allowed(_exception):
    return error("method not allowed", 405)
