import sqlite3
import os
import json
import hmac
import hashlib
import base64
import time
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, g

DB_PATH = os.environ.get("TASKS_DB", "./tasks.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "supersecretkey")
JWT_ALGO = "HS256"

def get_db():
    db = getattr(g, "db", None)
    if db is None:
        db = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        db.row_factory = sqlite3.Row
        g.db = db
    return db

def close_db(e=None):
    db = getattr(g, "db", None)
    if db is not None:
        db.close()

def create_app():
    app = Flask(__name__)
    app.teardown_appcontext(close_db)

    # Ensure DB exists and tables created
    init_db()

    # Helpers
    def json_resp(data, code=200):
        return jsonify(data), code

    def b64url_encode(b: bytes) -> str:
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    def b64url_decode(s: str) -> bytes:
        padding = "=" * (-len(s) % 4)
        return base64.urlsafe_b64decode(s + padding)

    def make_token(payload: dict, exp_seconds=3600):
        payload = payload.copy()
        payload["exp"] = int(time.time()) + exp_seconds
        payload_json = json.dumps(payload, separators=(",", ":")).encode()
        sig = hmac.new(JWT_SECRET.encode(), payload_json, hashlib.sha256).digest()
        return f"{b64url_encode(payload_json)}.{b64url_encode(sig)}"

    def verify_token(token: str):
        try:
            parts = token.split(".")
            if len(parts) != 2:
                return None
            payload_b, sig_b = parts
            payload_json = b64url_decode(payload_b)
            sig = b64url_decode(sig_b)
            expected = hmac.new(JWT_SECRET.encode(), payload_json, hashlib.sha256).digest()
            if not hmac.compare_digest(expected, sig):
                return None
            payload = json.loads(payload_json.decode())
            if payload.get("exp", 0) < int(time.time()):
                return None
            return payload
        except Exception:
            return None

    def auth_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                token = auth[len("Bearer "):]
                payload = verify_token(token)
                if payload:
                    g.user = get_user_by_id(payload.get("user_id"))
                    if g.user:
                        return f(*args, **kwargs)
            return json_resp({"error": "unauthorized"}, 401)
        return decorated

    # User utilities
    def get_user_by_id(user_id):
        db = get_db()
        row = db.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def get_user_by_username(username):
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None

    def hash_password(password: str, salt: bytes = None):
        if salt is None:
            salt = os.urandom(16)
        dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        return salt.hex() + ":" + dk.hex()

    def verify_password(stored: str, password: str) -> bool:
        try:
            salt_hex, dk_hex = stored.split(":")
            salt = bytes.fromhex(salt_hex)
            dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
            return hmac.compare_digest(dk.hex(), dk_hex)
        except Exception:
            return False

    # Routes
    @app.route('/register', methods=['POST'])
    def register():
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')
        if not username or not password:
            return json_resp({'error': 'username and password required'}, 400)
        if get_user_by_username(username):
            return json_resp({'error': 'username taken'}, 400)
        db = get_db()
        pwd_h = hash_password(password)
        cur = db.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, pwd_h))
        db.commit()
        user_id = cur.lastrowid
        return json_resp({'id': user_id, 'username': username}, 201)

    @app.route('/login', methods=['POST'])
    def login():
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')
        user = get_user_by_username(username)
        if not user or not verify_password(user['password_hash'], password):
            return json_resp({'error': 'invalid credentials'}, 401)
        token = make_token({'user_id': user['id']})
        return json_resp({'token': token})

    @app.route('/me')
    @auth_required
    def me():
        u = g.user
        return json_resp({'id': u['id'], 'username': u['username']})

    # Tasks endpoints
    def row_to_task(row):
        if row is None:
            return None
        d = dict(row)
        # convert dates
        for k in ('due_date','created_at','updated_at'):
            if d.get(k):
                d[k] = d[k]
        return d

    @app.route('/tasks', methods=['POST'])
    @auth_required
    def create_task():
        data = request.get_json() or {}
        title = data.get('title','').strip()
        if not title:
            return json_resp({'error':'title required'}, 400)
        description = data.get('description')
        status = data.get('status','pending')
        category = data.get('category')
        priority = data.get('priority','medium')
        due_date = data.get('due_date')
        assignee_id = data.get('assignee_id')
        db = get_db()
        now = datetime.utcnow().isoformat()
        cur = db.execute(
            'INSERT INTO tasks (title, description, status, category, priority, due_date, assignee_id, creator_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (title, description, status, category, priority, due_date, assignee_id, g.user['id'], now, now)
        )
        db.commit()
        tid = cur.lastrowid
        row = db.execute('SELECT * FROM tasks WHERE id = ?', (tid,)).fetchone()
        return json_resp({'task': row_to_task(row)}, 201)

    @app.route('/tasks', methods=['GET'])
    @auth_required
    def list_tasks():
        db = get_db()
        q = request.args.get('q')
        status = request.args.get('status')
        category = request.args.get('category')
        priority = request.args.get('priority')
        assignee = request.args.get('assignee_id')
        due_before = request.args.get('due_before')
        due_after = request.args.get('due_after')
        page = int(request.args.get('page', '1'))
        per_page = int(request.args.get('per_page', '10'))
        params = []
        where = []
        if q:
            where.append('(title LIKE ? OR description LIKE ?)')
            params.extend([f'%{q}%']*2)
        if status:
            where.append('status = ?')
            params.append(status)
        if category:
            where.append('category = ?')
            params.append(category)
        if priority:
            where.append('priority = ?')
            params.append(priority)
        if assignee:
            where.append('assignee_id = ?')
            params.append(assignee)
        if due_before:
            where.append('due_date <= ?')
            params.append(due_before)
        if due_after:
            where.append('due_date >= ?')
            params.append(due_after)
        where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''
        count_sql = f'SELECT COUNT(*) as c FROM tasks {where_sql}'
        total = db.execute(count_sql, params).fetchone()['c']
        offset = (page-1)*per_page
        sql = f'SELECT * FROM tasks {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?'
        rows = db.execute(sql, params + [per_page, offset]).fetchall()
        tasks = [row_to_task(r) for r in rows]
        return json_resp({'total': total, 'page': page, 'per_page': per_page, 'tasks': tasks})

    @app.route('/tasks/<int:task_id>', methods=['GET'])
    @auth_required
    def get_task(task_id):
        db = get_db()
        row = db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        if not row:
            return json_resp({'error':'not found'}, 404)
        return json_resp({'task': row_to_task(row)})

    @app.route('/tasks/<int:task_id>', methods=['PUT'])
    @auth_required
    def update_task(task_id):
        db = get_db()
        row = db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        if not row:
            return json_resp({'error':'not found'}, 404)
        task = dict(row)
        # allow only creator or assignee
        if g.user['id'] not in (task.get('creator_id'), task.get('assignee_id')):
            return json_resp({'error':'forbidden'}, 403)
        data = request.get_json() or {}
        fields = {}
        allowed = ('title','description','status','category','priority','due_date','assignee_id')
        for k in allowed:
            if k in data:
                fields[k] = data[k]
        if not fields:
            return json_resp({'error':'nothing to update'}, 400)
        fields['updated_at'] = datetime.utcnow().isoformat()
        set_sql = ','.join([f"{k} = ?" for k in fields.keys()])
        params = list(fields.values()) + [task_id]
        db.execute(f'UPDATE tasks SET {set_sql} WHERE id = ?', params)
        db.commit()
        row = db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        return json_resp({'task': row_to_task(row)})

    @app.route('/tasks/<int:task_id>', methods=['DELETE'])
    @auth_required
    def delete_task(task_id):
        db = get_db()
        row = db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        if not row:
            return json_resp({'error':'not found'}, 404)
        task = dict(row)
        if g.user['id'] != task.get('creator_id'):
            return json_resp({'error':'forbidden'}, 403)
        db.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        db.commit()
        return json_resp({'deleted': task_id})

    return app


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        status TEXT DEFAULT 'pending',
        category TEXT,
        priority TEXT DEFAULT 'medium',
        due_date TEXT,
        assignee_id INTEGER,
        creator_id INTEGER NOT NULL,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY(assignee_id) REFERENCES users(id),
        FOREIGN KEY(creator_id) REFERENCES users(id)
    );
    ''' )
    conn.commit()
    conn.close()


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
