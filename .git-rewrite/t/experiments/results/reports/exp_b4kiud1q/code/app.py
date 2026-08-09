import hashlib
import re
import time

from flask import Flask, jsonify, redirect, request, url_for

app = Flask(__name__)

URLS = {}
URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def _generate_code(url: str) -> str:
    return hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()[:6]


def _validate_url(url: str) -> bool:
    return bool(URL_RE.match(url))


@app.route("/shorten", methods=["POST"])
def shorten():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url or not _validate_url(url):
        return jsonify({"error": "A valid URL starting with http:// or https:// is required"}), 400

    code = _generate_code(url)
    URLS[code] = {"url": url, "created_at": int(time.time()), "hits": 0}
    return jsonify({"short_url": url_for("redirect_to_url", code=code, _external=True), "code": code}), 201


@app.route("/<code>")
def redirect_to_url(code):
    entry = URLS.get(code)
    if not entry:
        return jsonify({"error": "Not found"}), 404
    entry["hits"] += 1
    return redirect(entry["url"], code=302)


@app.route("/api/stats/<code>")
def stats(code):
    entry = URLS.get(code)
    if not entry:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"code": code, "url": entry["url"], "hits": entry["hits"], "created_at": entry["created_at"]})


@app.route("/api/<code>", methods=["DELETE"])
def delete_url(code):
    if code not in URLS:
        return jsonify({"error": "Not found"}), 404
    del URLS[code]
    return jsonify({"message": "Deleted"}), 200
