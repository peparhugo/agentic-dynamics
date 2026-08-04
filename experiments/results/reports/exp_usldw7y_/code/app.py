"""URL shortener REST API backed by SQLite."""
import secrets
import sqlite3
import string
from urllib.parse import urlparse

from flask import Flask, g, jsonify, redirect, request

ALPHABET = string.ascii_letters + string.digits
CODE_LEN = 7


def create_app(db_path=":memory:"):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DB_PATH"])
            g.db.row_factory = sqlite3.Row
            g.db.execute(
                """CREATE TABLE IF NOT EXISTS urls (
                    code TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    hits INTEGER NOT NULL DEFAULT 0
                )"""
            )
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def valid_url(url):
        try:
            p = urlparse(url)
            return p.scheme in ("http", "https") and bool(p.netloc)
        except ValueError:
            return False

    @app.post("/api/shorten")
    def shorten():
        data = request.get_json(silent=True) or {}
        url = data.get("url", "")
        if not valid_url(url):
            return jsonify(error="invalid or missing 'url' (must be http/https)"), 400

        db = get_db()
        custom = data.get("code")
        if custom is not None:
            if not (1 <= len(custom) <= 32 and all(c in ALPHABET for c in custom)):
                return jsonify(error="custom code must be 1-32 alphanumeric chars"), 400
            try:
                db.execute("INSERT INTO urls (code, url) VALUES (?, ?)", (custom, url))
            except sqlite3.IntegrityError:
                return jsonify(error="code already in use"), 409
            code = custom
        else:
            while True:
                code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LEN))
                try:
                    db.execute("INSERT INTO urls (code, url) VALUES (?, ?)", (code, url))
                    break
                except sqlite3.IntegrityError:
                    continue
        db.commit()
        return jsonify(code=code, url=url, short_url=f"{request.host_url}{code}"), 201

    @app.get("/<code>")
    def follow(code):
        db = get_db()
        row = db.execute("SELECT url FROM urls WHERE code = ?", (code,)).fetchone()
        if row is None:
            return jsonify(error="not found"), 404
        db.execute("UPDATE urls SET hits = hits + 1 WHERE code = ?", (code,))
        db.commit()
        return redirect(row["url"], code=302)

    @app.get("/api/urls/<code>")
    def stats(code):
        row = get_db().execute(
            "SELECT code, url, hits FROM urls WHERE code = ?", (code,)
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
    create_app("urls.db").run(debug=True)
