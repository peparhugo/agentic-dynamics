import secrets
import string
import validators
import re
from flask import Flask, request, jsonify, redirect, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from storage import URLStorage

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per hour"],
    storage_uri="memory://",
)

storage = URLStorage()

SHORT_CODE_LENGTH = 7
BASE_URL_RE = re.compile(r"^/[A-Za-z0-9_-]+$")


def _generate_short_code(length=SHORT_CODE_LENGTH):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/shorten", methods=["POST"])
@limiter.limit("10 per minute")
def shorten_url():
    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return jsonify({"error": "Missing 'url' in request body"}), 400

    url = data["url"].strip()

    if not validators.url(url):
        return jsonify({"error": "Invalid URL"}), 400

    short_code = _generate_short_code()
    while not storage.save(short_code, url):
        short_code = _generate_short_code()

    return jsonify({
        "short_code": short_code,
        "short_url": url_for("redirect_url", short_code=short_code, _external=True),
        "original_url": url,
    }), 201


@app.route("/<short_code>", methods=["GET"])
def redirect_url(short_code):
    if not BASE_URL_RE.match(f"/{short_code}"):
        return jsonify({"error": "Invalid short code format"}), 400

    entry = storage.get(short_code)
    if entry is None:
        return jsonify({"error": "Short code not found"}), 404

    return redirect(entry["url"], code=301)


@app.route("/stats/<short_code>", methods=["GET"])
def stats_url(short_code):
    data = storage.stats(short_code)
    if data is None:
        return jsonify({"error": "Short code not found"}), 404
    return jsonify(data)


@app.route("/urls", methods=["GET"])
def list_urls():
    all_entries = storage.all_urls()
    result = []
    for code, entry in all_entries.items():
        result.append({
            "short_code": code,
            "url": entry["url"],
            "created_at": entry["created_at"],
            "access_count": entry["access_count"],
        })
    return jsonify(result)
