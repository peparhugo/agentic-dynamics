import re
from urllib.parse import urljoin, urlparse

from flask import Flask, g, jsonify, redirect, request

from .codes import CodeGenerator
from .models import Storage
from .rate_limit import RateLimiter

CUSTOM_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,32}$")


class ValidationError(Exception):
    pass


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=":memory:",
        CODE_LENGTH=6,
        SHORTEN_RATE_LIMIT=10,
        SHORTEN_RATE_WINDOW=60,
        BASE_URL=None,
    )
    if config:
        app.config.update(config)

    storage = Storage(app.config["DATABASE"])
    generator = CodeGenerator(
        storage.code_exists, length=app.config["CODE_LENGTH"]
    )
    limiter = RateLimiter(
        app.config["SHORTEN_RATE_LIMIT"],
        app.config["SHORTEN_RATE_WINDOW"],
    )

    @app.teardown_appcontext
    def _teardown(exception):
        g.pop("client_ip", None)

    def _client_ip():
        return request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()

    def _validate_url(url):
        if not url or len(url) > 2048:
            raise ValidationError("url is required and must be <= 2048 chars")
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValidationError("url must be an absolute http(s) URL")

    def _short_url(code):
        base = app.config["BASE_URL"]
        if base:
            return urljoin(base.rstrip("/") + "/", code)
        return request.host_url.rstrip("/") + "/" + code

    @app.errorhandler(ValidationError)
    def _validation_error(err):
        return jsonify({"error": str(err)}), 400

    @app.errorhandler(404)
    def _not_found(err):
        if request.path.startswith("/api/"):
            return jsonify({"error": "not found"}), 404
        return err

    @app.post("/api/shorten")
    def shorten():
        ip = _client_ip()
        allowed, count, limit, retry_after = limiter.allow(ip)
        if not allowed:
            resp = jsonify({"error": "rate limit exceeded"})
            resp.headers["Retry-After"] = str(retry_after)
            return resp, 429

        data = request.get_json(silent=True) or {}
        url = data.get("url")
        try:
            _validate_url(url)
            custom = data.get("custom_code")
            if custom is not None:
                if not CUSTOM_CODE_PATTERN.match(custom):
                    raise ValidationError(
                        "custom_code must be 3-32 chars of [A-Za-z0-9_-]"
                    )
                if storage.code_exists(custom):
                    return jsonify({"error": "custom_code already in use"}), 409
                code = custom
            else:
                code = generator.generate()
            storage.create_url(code, url)
        except ValidationError as err:
            return jsonify({"error": str(err)}), 400
        except Exception:
            app.logger.exception("shorten failed")
            return jsonify({"error": "internal error"}), 500

        return (
            jsonify(
                {
                    "short_code": code,
                    "short_url": _short_url(code),
                    "original_url": url,
                }
            ),
            201,
        )

    @app.get("/api/stats/<code>")
    def stats(code):
        entry = storage.get_url(code)
        if entry is None:
            return jsonify({"error": "not found"}), 404
        stats_data = storage.click_stats(code)
        return jsonify(
            {
                "short_code": code,
                "original_url": entry["url"],
                "created_at": entry["created_at"],
                **stats_data,
            }
        )

    @app.get("/r/<code>")
    def redirect_code(code):
        entry = storage.get_url(code)
        if entry is None:
            return jsonify({"error": "not found"}), 404
        storage.record_click(
            code,
            _client_ip(),
            request.headers.get("User-Agent"),
            request.headers.get("Referer"),
        )
        return redirect(entry["url"], code=302)

    @app.delete("/api/codes/<code>")
    def delete_code(code):
        entry = storage.get_url(code)
        if entry is None:
            return jsonify({"error": "not found"}), 404
        storage.delete_url(code)
        return jsonify({"deleted": code}), 200

    return app
