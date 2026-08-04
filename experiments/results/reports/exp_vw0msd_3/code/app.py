import sqlite3
import string
from urllib.parse import urlparse

from flask import Flask, g, jsonify, redirect, request

ALPHABET = string.digits + string.ascii_letters  # base62


def encode(n: int) -> str:
    if n == 0:
        return ALPHABET[0]
    out = []
    while n:
        n, r = divmod(n, 62)
        out.append(ALPHABET[r])
    return "".join(reversed(out))


def is_valid_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except ValueError:
        return False


def create_app(db_path: str = "urls.db") -> Flask:
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

    with app.app_context():
        get_db().execute(
            """CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                code TEXT UNIQUE,
                visits INTEGER NOT NULL DEFAULT 0
            )"""
        )
        get_db().commit()

    @app.post("/api/shorten")
    def shorten():
        data = request.get_json(silent=True) or {}
        url = data.get("url", "")
        if not is_valid_url(url):
            return jsonify(error="invalid url"), 400
        db = get_db()
        cur = db.execute("INSERT INTO urls (url) VALUES (?)", (url,))
        code = encode(cur.lastrowid)
        db.execute("UPDATE urls SET code = ? WHERE id = ?", (code, cur.lastrowid))
        db.commit()
        return jsonify(code=code, short_url=request.host_url + code, url=url), 201

    @app.get("/api/urls/<code>")
    def stats(code):
        row = get_db().execute(
            "SELECT url, code, visits FROM urls WHERE code = ?", (code,)
        ).fetchone()
        if row is None:
            return jsonify(error="not found"), 404
        return jsonify(dict(row))

    @app.get("/<code>")
    def follow(code):
        db = get_db()
        row = db.execute("SELECT url FROM urls WHERE code = ?", (code,)).fetchone()
        if row is None:
            return jsonify(error="not found"), 404
        db.execute("UPDATE urls SET visits = visits + 1 WHERE code = ?", (code,))
        db.commit()
        return redirect(row["url"], code=302)

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
