import sqlite3
import string
import secrets

from flask import Flask, request, jsonify, redirect, g

app = Flask(__name__)
DATABASE = "urls.db"
BASE62 = string.digits + string.ascii_lowercase + string.ascii_uppercase


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
    return db


@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                url TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        db.execute("CREATE INDEX IF NOT EXISTS idx_code ON urls(code)")
        db.commit()


def generate_code(length=6):
    return "".join(secrets.choice(BASE62) for _ in range(length))


@app.route("/api/shorten", methods=["POST"])
def shorten():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400

    db = get_db()
    for _ in range(10):
        code = generate_code()
        try:
            db.execute("INSERT INTO urls (code, url) VALUES (?, ?)", (code, url))
            db.commit()
            return jsonify({"code": code, "short_url": f"/{code}", "url": url}), 201
        except sqlite3.IntegrityError:
            db.rollback()
    return jsonify({"error": "could not generate unique code"}), 500


@app.route("/api/urls", methods=["GET"])
def list_urls():
    db = get_db()
    rows = db.execute("SELECT code, url, created_at FROM urls ORDER BY created_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/<code>", methods=["GET"])
def get_url(code):
    db = get_db()
    row = db.execute("SELECT code, url, created_at FROM urls WHERE code = ?", (code,)).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(dict(row))


@app.route("/<code>", methods=["GET"])
def redirect_to_url(code):
    db = get_db()
    row = db.execute("SELECT url FROM urls WHERE code = ?", (code,)).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return redirect(row["url"], 301)


init_db()
