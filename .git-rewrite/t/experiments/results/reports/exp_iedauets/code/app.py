import hashlib
import re

from flask import Flask, jsonify, redirect, request, url_for

app = Flask(__name__)
urls = {}

URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def _shorten(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:8]


@app.route("/", methods=["GET"])
def index():
    return jsonify({"message": "URL shortener v1"}), 200


@app.route("/shorten", methods=["POST"])
def shorten():
    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return jsonify({"error": "missing 'url' field"}), 400

    long_url = data["url"]
    if not URL_RE.match(long_url):
        return jsonify({"error": "invalid URL"}), 400

    code = _shorten(long_url)
    urls[code] = long_url
    short_url = url_for("redirect_url", code=code, _external=True)
    return jsonify({"short_url": short_url, "code": code}), 201


@app.route("/<code>", methods=["GET"])
def redirect_url(code):
    long_url = urls.get(code)
    if not long_url:
        return jsonify({"error": "not found"}), 404
    return redirect(long_url, 302)


if __name__ == "__main__":
    app.run(debug=True)
