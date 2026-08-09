import threading
import time
from itertools import count
from urllib.parse import urlparse

from flask import Flask, jsonify, redirect, request

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(ALPHABET)


def _encode(n: int) -> str:
    if n == 0:
        return ALPHABET[0]
    chars = []
    while n > 0:
        n, rem = divmod(n, BASE)
        chars.append(ALPHABET[rem])
    return "".join(reversed(chars))


app = Flask(__name__)
_store: dict[str, dict] = {}
_counter = count(1)
_lock = threading.Lock()
_next_ttl_clean = time.monotonic() + 3600


def _expire_stale():
    global _next_ttl_clean
    now = time.time()
    if time.monotonic() < _next_ttl_clean:
        return
    for sid in list(_store):
        ttl = _store[sid].get("ttl")
        if ttl and now > ttl:
            del _store[sid]
    _next_ttl_clean = time.monotonic() + 3600


@app.route("/shorten", methods=["POST"])
def shorten():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return jsonify({"error": "url must start with http:// or https://"}), 400
    ttl = data.get("ttl")
    if ttl is not None:
        try:
            ttl = float(ttl)
        except (TypeError, ValueError):
            return jsonify({"error": "ttl must be a number"}), 400
        if ttl <= 0:
            return jsonify({"error": "ttl must be positive"}), 400

    with _lock:
        short_id = _encode(next(_counter))
        _store[short_id] = {
            "url": url,
            "created": time.time(),
            "hits": 0,
            "ttl": time.time() + ttl if ttl else None,
        }
    return jsonify({"short_id": short_id, "url": url, "ttl": ttl}), 201


@app.route("/<short_id>")
def resolve(short_id: str):
    _expire_stale()
    entry = _store.get(short_id)
    if not entry:
        return jsonify({"error": "not found"}), 404
    ttl = entry.get("ttl")
    if ttl and time.time() > ttl:
        with _lock:
            _store.pop(short_id, None)
        return jsonify({"error": "expired"}), 410
    with _lock:
        entry["hits"] += 1
    return redirect(entry["url"], code=302)


@app.route("/stats/<short_id>")
def stats(short_id: str):
    _expire_stale()
    entry = _store.get(short_id)
    if not entry:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "short_id": short_id,
        "url": entry["url"],
        "hits": entry["hits"],
        "created": entry["created"],
        "ttl": entry.get("ttl"),
    })
