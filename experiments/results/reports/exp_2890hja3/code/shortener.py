"""URL shortener — Flask REST API with SQLite storage."""
import re
import secrets
import sqlite3
import string
from urllib.parse import urlparse

from flask import Flask, g, jsonify, redirect, request

ALPHABET = string.ascii_letters + string.digits
CODE_LEN = 7
CODE_RE = re.compile(rf"^[A-Za-z0-9]{{1,{CODE_LEN * 2}}}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
    code TEXT PRIMARY KEY,
    url  TEXT NOT NULL,
    hits INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def create_app(db_path=":memory:"):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path

    # In-memory SQLite dies with each connection, so keep one alive.
    if db_path == ":memory:":
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        app.config["DB_CONN"] = conn
    else:
        with sqlite3.connect(db_path) as conn:
            conn.executescript(SCHEMA)

    def get_db():
        if "DB_CONN" in app.config:
            return app.config["DB_CONN"]
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DB_PATH"])
            g.db.row_factory = sqlite3.Row
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

    def gen_code(db):
        for _ in range(10):
            code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LEN))
            if not db.execute("SELECT 1 FROM links WHERE code=?", (code,)).fetchone():
                return code
        raise RuntimeError("could not generate unique code")

    # ---- REST API ----

    @app.post("/api/links")
    def create_link():
        data = request.get_json(silent=True) or {}
        url = data.get("url", "")
        if not valid_url(url):
            return jsonify(error="invalid or missing 'url' (must be http/https)"), 400

        db = get_db()
        custom = data.get("code")
        if custom is not None:
            if not CODE_RE.match(str(custom)):
                return jsonify(error="custom code must be alphanumeric"), 400
            if db.execute("SELECT 1 FROM links WHERE code=?", (custom,)).fetchone():
                return jsonify(error="code already in use"), 409
            code = custom
        else:
            code = gen_code(db)

        db.execute("INSERT INTO links (code, url) VALUES (?, ?)", (code, url))
        db.commit()
        return jsonify(code=code, url=url, short_url=request.host_url + code), 201

    @app.get("/api/links/<code>")
    def get_link(code):
        row = get_db().execute(
            "SELECT code, url, hits, created_at FROM links WHERE code=?", (code,)
        ).fetchone()
        if row is None:
            return jsonify(error="not found"), 404
        return jsonify(dict(row))

    @app.delete("/api/links/<code>")
    def delete_link(code):
        db = get_db()
        cur = db.execute("DELETE FROM links WHERE code=?", (code,))
        db.commit()
        if cur.rowcount == 0:
            return jsonify(error="not found"), 404
        return "", 204

    # ---- Redirect ----

    @app.get("/<code>")
    def follow(code):
        db = get_db()
        row = db.execute("SELECT url FROM links WHERE code=?", (code,)).fetchone()
        if row is None:
            return jsonify(error="not found"), 404
        db.execute("UPDATE links SET hits = hits + 1 WHERE code=?", (code,))
        db.commit()
        return redirect(row["url"], code=302)

    return app


if __name__ == "__main__":
    create_app("links.db").run(debug=True)
