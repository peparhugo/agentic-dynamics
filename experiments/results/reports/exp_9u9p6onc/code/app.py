"""URL shortener with REST API backed by SQLite."""

import re
import sqlite3
import string

from flask import Flask, g, jsonify, redirect, request

ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase
CODE_RE = re.compile(r"^[0-9a-zA-Z]{1,16}$")
URL_RE = re.compile(r"^https?://\S+$")


def encode(n: int) -> str:
    """Base62-encode a positive integer."""
    if n == 0:
        return ALPHABET[0]
    out = []
    while n:
        n, r = divmod(n, 62)
        out.append(ALPHABET[r])
    return "".join(reversed(out))


def create_app(db_path: str = "urls.db") -> Flask:
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path

    def get_db() -> sqlite3.Connection:
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DB_PATH"])
            g.db.row_factory = sqlite3.Row
            g.db.execute(
                """CREATE TABLE IF NOT EXISTS urls (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       code TEXT UNIQUE,
                       url TEXT NOT NULL,
                       visits INTEGER NOT NULL DEFAULT 0
                   )"""
            )
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.post("/api/shorten")
    def shorten():
        data = request.get_json(silent=True) or {}
        url = data.get("url", "")
        if not URL_RE.match(url):
            return jsonify(error="invalid url, must start with http(s)://"), 400

        db = get_db()
        row = db.execute("SELECT code FROM urls WHERE url = ?", (url,)).fetchone()
        if row:
            code = row["code"]
        else:
            cur = db.execute("INSERT INTO urls (url) VALUES (?)", (url,))
            code = encode(cur.lastrowid)
            db.execute("UPDATE urls SET code = ? WHERE id = ?", (code, cur.lastrowid))
            db.commit()
        return jsonify(code=code, short_url=request.host_url + code, url=url), 201

    @app.get("/api/urls/<code>")
    def stats(code):
        row = _lookup(get_db(), code)
        if row is None:
            return jsonify(error="not found"), 404
        return jsonify(code=row["code"], url=row["url"], visits=row["visits"])

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
        row = _lookup(db, code)
        if row is None:
            return jsonify(error="not found"), 404
        db.execute("UPDATE urls SET visits = visits + 1 WHERE code = ?", (code,))
        db.commit()
        return redirect(row["url"], code=302)

    def _lookup(db, code):
        if not CODE_RE.match(code):
            return None
        return db.execute("SELECT * FROM urls WHERE code = ?", (code,)).fetchone()

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
