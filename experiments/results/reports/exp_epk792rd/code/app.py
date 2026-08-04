import hashlib
from flask import Flask, request, jsonify, redirect

app = Flask(__name__)
urls = {}


def shorten(url):
    h = hashlib.sha256(url.encode()).hexdigest()[:6]
    urls[h] = url
    return h


@app.route("/shorten", methods=["POST"])
def create():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "")
    if not url:
        return jsonify({"error": "url is required"}), 400
    return jsonify({"short_id": shorten(url), "original": url}), 201


@app.route("/<short_id>", methods=["GET"])
def redirect_url(short_id):
    url = urls.get(short_id)
    if not url:
        return jsonify({"error": "not found"}), 404
    return redirect(url)


@app.route("/urls", methods=["GET"])
def list_urls():
    return jsonify(urls), 200


if __name__ == "__main__":
    app.run(debug=True)
