import hashlib
import os
import sqlite3
import string
import time
import uuid
from datetime import datetime, timedelta
from flask import Flask, jsonify, g, redirect, request, abort

BASE62 = string.digits + string.ascii_letters


def base62_encode(n: int) -> str:
    if n == 0:
        return BASE62[0]
    out = []
    base = len(BASE62)
    while n:
        n, r = divmod(n, base)
        out.append(BASE62[r])
    return ''.join(reversed(out))


def get_db():
    db = getattr(g, '_db', None)
    if db is None:
        path = current_app_config().get('DATABASE')
        db = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
        db.row_factory = sqlite3.Row
        g._db = db
    return db


def current_app_config():
    # lazy import to avoid circular when used in tests
    from flask import current_app
    return current_app.config


def init_db(conn):
    c = conn.cursor()
    c.executescript(
        """
CREATE TABLE IF NOT EXISTS urls (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    original_url TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS clicks (
    id INTEGER PRIMARY KEY,
    url_id INTEGER NOT NULL,
    ts TIMESTAMP NOT NULL,
    ip TEXT,
    user_agent TEXT,
    FOREIGN KEY(url_id) REFERENCES urls(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS rate_limits (
    id INTEGER PRIMARY KEY,
    ip TEXT NOT NULL,
    ts TIMESTAMP NOT NULL
);
"""
    )
    conn.commit()


def create_app(test_config=None):
    app = Flask(__name__)
    # defaults
    app.config.update(
        DATABASE=os.environ.get('URLSHORT_DB', 'urlshort.db'),
        RATE_LIMIT=5,  # requests per minute per IP
        SHORTCODE_LENGTH=7,
        BASE_URL=os.environ.get('BASE_URL', 'http://localhost/'),
    )
    if test_config:
        app.config.update(test_config)

    @app.teardown_appcontext
    def close_db(exception=None):
        db = getattr(g, '_db', None)
        if db is not None:
            db.close()

    # Ensure database exists and schema initialized right away. Tests will still
    # initialize their own DB in conftest, but for typical runs create the file
    # and schema if missing.
    path = app.config['DATABASE']
    try:
        need_init = (not os.path.exists(path)) or path == ':memory:'
    except Exception:
        # In some environments path may not be a filesystem path; attempt to
        # open and initialize anyway.
        need_init = True
    if need_init:
        conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
        init_db(conn)
        conn.close()

    def generate_code(original_url: str) -> str:
        # Try a handful of variants to avoid collisions. Use sha256 + uuid + counter.
        for counter in range(0, 10):
            salt = uuid.uuid4().hex
            s = f"{original_url}|{salt}|{counter}|{time.time()}"
            h = hashlib.sha256(s.encode()).digest()
            n = int.from_bytes(h, 'big')
            code = base62_encode(n)[: app.config['SHORTCODE_LENGTH']]
            # ensure code is alphanumeric-ish
            if code:
                # check uniqueness
                db = get_db()
                cur = db.execute('SELECT 1 FROM urls WHERE code = ?', (code,))
                if cur.fetchone() is None:
                    return code
        # fallback to uuid
        return uuid.uuid4().hex[: app.config['SHORTCODE_LENGTH']]

    def check_rate_limit(ip: str) -> bool:
        db = get_db()
        window = datetime.utcnow() - timedelta(seconds=60)
        cur = db.execute('SELECT COUNT(*) as c FROM rate_limits WHERE ip = ? AND ts > ?', (ip, window))
        row = cur.fetchone()
        count = row['c'] if row else 0
        return count >= app.config['RATE_LIMIT']

    def add_rate_record(ip: str):
        db = get_db()
        db.execute('INSERT INTO rate_limits (ip, ts) VALUES (?, ?)', (ip, datetime.utcnow()))
        # purge old records occasionally
        db.execute('DELETE FROM rate_limits WHERE ts < ?', (datetime.utcnow() - timedelta(seconds=3600),))
        db.commit()

    @app.route('/shorten', methods=['POST'])
    def shorten():
        ip = request.remote_addr or request.environ.get('REMOTE_ADDR') or 'unknown'
        if check_rate_limit(ip):
            return jsonify({'error': 'rate limit exceeded'}), 429
        data = request.get_json() or {}
        original_url = data.get('url')
        if not original_url:
            return jsonify({'error': 'url required'}), 400
        custom = data.get('custom_code')
        db = get_db()
        if custom:
            # validate
            if len(custom) > 128:
                return jsonify({'error': 'custom code too long'}), 400
            cur = db.execute('SELECT 1 FROM urls WHERE code = ?', (custom,))
            if cur.fetchone():
                return jsonify({'error': 'code already exists'}), 409
            code = custom
        else:
            code = generate_code(original_url)
        created_at = datetime.utcnow()
        try:
            db.execute('INSERT INTO urls (code, original_url, created_at) VALUES (?, ?, ?)', (code, original_url, created_at))
            db.commit()
        except sqlite3.IntegrityError:
            return jsonify({'error': 'collision'}), 500
        add_rate_record(ip)
        short_url = app.config['BASE_URL'].rstrip('/') + '/' + code
        return jsonify({'code': code, 'short_url': short_url}), 201

    @app.route('/analytics/<code>', methods=['GET'])
    def analytics(code):
        db = get_db()
        cur = db.execute('SELECT id, original_url, created_at FROM urls WHERE code = ?', (code,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        url_id = row['id']
        cur = db.execute('SELECT COUNT(*) as c FROM clicks WHERE url_id = ?', (url_id,))
        clicks = cur.fetchone()['c']
        cur = db.execute('SELECT ts, ip, user_agent FROM clicks WHERE url_id = ? ORDER BY ts DESC LIMIT 50', (url_id,))
        recent = [dict(ts=r['ts'], ip=r['ip'], user_agent=r['user_agent']) for r in cur.fetchall()]
        return jsonify({'code': code, 'original_url': row['original_url'], 'created_at': row['created_at'], 'clicks': clicks, 'recent': recent})

    @app.route('/<code>', methods=['GET'])
    def redirect_code(code):
        db = get_db()
        cur = db.execute('SELECT id, original_url FROM urls WHERE code = ?', (code,))
        row = cur.fetchone()
        if not row:
            abort(404)
        url_id = row['id']
        # record click
        ip = request.remote_addr or request.environ.get('REMOTE_ADDR') or 'unknown'
        ua = request.headers.get('User-Agent')
        db.execute('INSERT INTO clicks (url_id, ts, ip, user_agent) VALUES (?, ?, ?, ?)', (url_id, datetime.utcnow(), ip, ua))
        db.commit()
        return redirect(row['original_url'], code=302)

    return app
