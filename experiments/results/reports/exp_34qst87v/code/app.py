import secrets
import string
import re

from flask import Flask, request, jsonify, redirect

from storage import URLStorage
from rate_limiter import RateLimiter

app = Flask(__name__)
storage = URLStorage()
rate_limiter = RateLimiter(max_requests=10, window_seconds=60)

CODE_LENGTH = 6
ALPHABET = string.ascii_letters + string.digits
URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


def _generate_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def _client_id() -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


@app.route("/shorten", methods=["POST"])
def shorten():
    if not rate_limiter.is_allowed(_client_id()):
        return jsonify({"error": "rate limit exceeded"}), 429

    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return jsonify({"error": "missing 'url' in request body"}), 400

    raw_url = data["url"].strip()
    if not URL_RE.match(raw_url):
        return jsonify({"error": "invalid URL format"}), 400

    for _ in range(10):
        code = _generate_code()
        if not storage.exists(code):
            storage.save(code, raw_url)
            return jsonify({"short_code": code, "short_url": f"/{code}"}), 201

    return jsonify({"error": "could not generate unique short code"}), 500


@app.route("/<code>", methods=["GET"])
def resolve(code: str):
    url = storage.get(code)
    if url is None:
        return jsonify({"error": "short code not found"}), 404
    return redirect(url, code=302)


@app.route("/<code>/stats", methods=["GET"])
def stats(code: str):
    data = storage.stats(code)
    if data is None:
        return jsonify({"error": "short code not found"}), 404
    return jsonify(data), 200
