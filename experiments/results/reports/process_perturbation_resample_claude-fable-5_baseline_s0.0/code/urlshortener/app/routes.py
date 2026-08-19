from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, redirect, request

from app.extensions import db, limiter
from app.models import Click, URL
from app.shortener import generate_unique_code, is_valid_code, is_valid_url

api = Blueprint("api", __name__)
redirects = Blueprint("redirects", __name__)


def _base_url():
    return current_app.config.get("BASE_URL", request.host_url)


@api.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@api.post("/api/shorten")
@limiter.limit(lambda: current_app.config["SHORTEN_RATE_LIMIT"])
def shorten():
    payload = request.get_json(silent=True) or {}
    long_url = payload.get("url")
    custom_code = payload.get("custom_code")
    expires_in_days = payload.get("expires_in_days")

    if not is_valid_url(long_url):
        return jsonify({"error": "A valid 'url' (http/https) field is required"}), 400

    if custom_code is not None:
        if not is_valid_code(custom_code):
            return (
                jsonify(
                    {
                        "error": "custom_code must be 1-16 alphanumeric characters"
                    }
                ),
                400,
            )
        if URL.query.filter_by(short_code=custom_code).first() is not None:
            return jsonify({"error": "custom_code already in use"}), 409
        short_code = custom_code
    else:
        short_code = generate_unique_code(
            min_length=current_app.config.get("SHORT_CODE_LENGTH", 6)
        )

    expires_at = None
    if expires_in_days is not None:
        try:
            expires_in_days = float(expires_in_days)
        except (TypeError, ValueError):
            return jsonify({"error": "expires_in_days must be numeric"}), 400
        if expires_in_days <= 0:
            return jsonify({"error": "expires_in_days must be positive"}), 400
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    url = URL(short_code=short_code, long_url=long_url, expires_at=expires_at)
    db.session.add(url)
    db.session.commit()

    return jsonify(url.to_dict(base_url=_base_url())), 201


@api.get("/api/urls/<short_code>")
def get_url(short_code):
    url = URL.query.filter_by(short_code=short_code).first()
    if url is None:
        return jsonify({"error": "short code not found"}), 404
    return jsonify(url.to_dict(base_url=_base_url()))


@api.delete("/api/urls/<short_code>")
def delete_url(short_code):
    url = URL.query.filter_by(short_code=short_code).first()
    if url is None:
        return jsonify({"error": "short code not found"}), 404
    db.session.delete(url)
    db.session.commit()
    return "", 204


@api.get("/api/urls/<short_code>/analytics")
def analytics(short_code):
    url = URL.query.filter_by(short_code=short_code).first()
    if url is None:
        return jsonify({"error": "short code not found"}), 404

    clicks = url.clicks.order_by(Click.clicked_at.desc()).all()

    by_day = {}
    referrers = {}
    for click in clicks:
        day = click.clicked_at.strftime("%Y-%m-%d")
        by_day[day] = by_day.get(day, 0) + 1
        ref = click.referrer or "direct"
        referrers[ref] = referrers.get(ref, 0) + 1

    return jsonify(
        {
            "short_code": url.short_code,
            "total_clicks": url.click_count,
            "clicks_by_day": by_day,
            "top_referrers": sorted(
                referrers.items(), key=lambda kv: kv[1], reverse=True
            ),
            "recent_clicks": [c.to_dict() for c in clicks[:50]],
        }
    )


@redirects.get("/<short_code>")
@limiter.limit(lambda: current_app.config["REDIRECT_RATE_LIMIT"])
def resolve(short_code):
    url = URL.query.filter_by(short_code=short_code).first()
    if url is None:
        return jsonify({"error": "short code not found"}), 404
    if url.is_expired():
        return jsonify({"error": "short code has expired"}), 410

    click = Click(
        url_id=url.id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        referrer=request.referrer,
    )
    url.click_count += 1
    db.session.add(click)
    db.session.commit()

    return redirect(url.long_url, code=302)
