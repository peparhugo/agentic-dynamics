"""URL shortener REST API."""
import secrets
import sqlite3
import string
from urllib.parse import urlparse

from flask import Flask, g, jsonify, redirect, request

ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 7

SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    code TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    clicks INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_urls_url ON urls(url);
"""


def create_app(db_path="urls.db"):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DB_PATH"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)

    def generate_code(db):
        while True:
            code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
            if not db.execute("SELECT 1 FROM urls WHERE code = ?", (code,)).fetchone():
                return code

    def valid_url(url):
        try:
            parts = urlparse(url)
            return parts.scheme in ("http", "https") and bool(parts.netloc)
        except ValueError:
            return False

    @app.post("/api/shorten")
    def shorten():
        data = request.get_json(silent=True) or {}
        url = data.get("url", "").strip()
        if not url:
            return jsonify(error="'url' is required"), 400
        if not valid_url(url):
            return jsonify(error="invalid URL; must be http(s) with a host"), 400

        db = get_db()
        custom = data.get("code")
        if custom is not None:
            if not (1 <= len(custom) <= 32 and all(c in ALPHABET for c in custom)):
                return jsonify(error="code must be 1-32 alphanumeric characters"), 400
            if db.execute("SELECT 1 FROM urls WHERE code = ?", (custom,)).fetchone():
                return jsonify(error="code already in use"), 409
            code = custom
        else:
            row = db.execute("SELECT code FROM urls WHERE url = ?", (url,)).fetchone()
            if row:
                return jsonify(code=row["code"], url=url,
                               short_url=request.host_url + row["code"]), 200
            code = generate_code(db)

        db.execute("INSERT INTO urls (code, url) VALUES (?, ?)", (code, url))
        db.commit()
        return jsonify(code=code, url=url, short_url=request.host_url + code), 201

    @app.get("/<code>")
    def follow(code):
        db = get_db()
        row = db.execute("SELECT url FROM urls WHERE code = ?", (code,)).fetchone()
        if row is None:
            return jsonify(error="not found"), 404
        db.execute("UPDATE urls SET clicks = clicks + 1 WHERE code = ?", (code,))
        db.commit()
        return redirect(row["url"], code=302)

    @app.get("/api/stats/<code>")
    def stats(code):
        row = get_db().execute(
            "SELECT code, url, clicks, created_at FROM urls WHERE code = ?", (code,)
        ).fetchone()
        if row is None:
            return jsonify(error="not found"), 404
        return jsonify(dict(row))

    @app.delete("/api/urls/<code>")
    def delete(code):
        db = get_db()
        cur = db.execute("DELETE FROM urls WHERE code = ?", (code,))
        db.commit()
        if cur.rowcount == 0:
            return jsonify(error="not found"), 404
        return "", 204

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
