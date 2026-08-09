import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import Flask, jsonify, redirect, request

app = Flask(__name__)

urls = {}


def _generate_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:8]


def _valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return bool(parsed.scheme in ("http", "https") and parsed.netloc)


@app.route("/shorten", methods=["POST"])
def shorten():
    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return jsonify({"error": "Missing 'url' in request body"}), 400

    url = data["url"].strip()
    if not _valid_url(url):
        return jsonify({"error": "Invalid URL. Must start with http:// or https://"}), 400

    short_id = _generate_id(url)
    urls[short_id] = {
        "url": url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "clicks": 0,
    }
    return jsonify({"short_id": short_id, "short_url": f"/{short_id}"}), 201


@app.route("/<short_id>", methods=["GET"])
def redirect_to_url(short_id):
    entry = urls.get(short_id)
    if not entry:
        return jsonify({"error": "Not found"}), 404

    entry["clicks"] += 1
    return redirect(entry["url"], code=302)


@app.route("/stats/<short_id>", methods=["GET"])
def stats(short_id):
    entry = urls.get(short_id)
    if not entry:
        return jsonify({"error": "Not found"}), 404

    return jsonify({
        "short_id": short_id,
        "url": entry["url"],
        "clicks": entry["clicks"],
        "created_at": entry["created_at"],
    })


if __name__ == "__main__":
    app.run(debug=True)
