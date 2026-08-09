import hashlib
import re
import time
from flask import Flask, jsonify, redirect, request, url_for

app = Flask(__name__)
_urls: dict[str, dict] = {}

URL_RE = re.compile(r"^https?://", re.I)
HASH_BYTES = 4


def _hash(url: str) -> str:
    seed = f"{url}{time.time()}".encode()
    return hashlib.blake2b(seed, digest_size=HASH_BYTES).hexdigest()


@app.route("/shorten", methods=["POST"])
def shorten():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400
    if not URL_RE.match(url):
        return jsonify({"error": "url must start with http:// or https://"}), 400

    sid = _hash(url)
    short_url = url_for("redirect_to", sid=sid, _external=True)
    _urls[sid] = {"id": sid, "url": url, "short_url": short_url}
    return jsonify(_urls[sid]), 201


@app.route("/<sid>")
def redirect_to(sid: str):
    entry = _urls.get(sid)
    if not entry:
        return jsonify({"error": "not found"}), 404
    return redirect(entry["url"], 302)


@app.route("/api/urls")
def list_urls():
    return jsonify(list(_urls.values()))


@app.route("/api/urls/<sid>")
def get_url(sid: str):
    entry = _urls.get(sid)
    if not entry:
        return jsonify({"error": "not found"}), 404
    return jsonify(entry)


if __name__ == "__main__":
    app.run(debug=True)
