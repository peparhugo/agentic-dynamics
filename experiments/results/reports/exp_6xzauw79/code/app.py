"""URL shortener REST API."""
import re
import sqlite3
import string

from flask import Flask, g, jsonify, redirect, request

ALPHABET = string.ascii_letters + string.digits
URL_RE = re.compile(r"^https?://\S+$")


def encode(n: int) -> str:
    """Base62-encode a positive integer."""
    chars = []
    while True:
        n, r = divmod(n, 62)
        chars.append(ALPHABET[r])
        if n == 0:
            return "".join(reversed(chars))


def create_app(db_path: str = "urls.db") -> Flask:
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path

    def get_db() -> sqlite3.Connection:
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
                code TEXT UNIQUE NOT NULL,
                url TEXT NOT NULL,
                clicks INTEGER NOT NULL DEFAULT 0
            )"""
        )
        get_db().commit()

    @app.post("/api/shorten")
    def shorten():
        data = request.get_json(silent=True) or {}
        url = data.get("url", "").strip()
        if not URL_RE.match(url):
            return jsonify(error="invalid url; must start with http:// or https://"), 400
        db = get_db()
        cur = db.execute("INSERT INTO urls (code, url) VALUES ('', ?)", (url,))
        code = encode(cur.lastrowid)
        db.execute("UPDATE urls SET code = ? WHERE id = ?", (code, cur.lastrowid))
        db.commit()
        return jsonify(code=code, url=url, short_url=f"{request.host_url}{code}"), 201

    @app.get("/api/urls/<code>")
    def info(code):
        row = get_db().execute(
            "SELECT code, url, clicks FROM urls WHERE code = ?", (code,)
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

    @app.get("/<code>")
    def follow(code):
        db = get_db()
        row = db.execute("SELECT url FROM urls WHERE code = ?", (code,)).fetchone()
        if row is None:
            return jsonify(error="not found"), 404
        db.execute("UPDATE urls SET clicks = clicks + 1 WHERE code = ?", (code,))
        db.commit()
        return redirect(row["url"], code=302)

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
