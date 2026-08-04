import json
import re
import secrets
import socket
import string
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Deque, Dict, Optional, Tuple
import sqlite3


# Simple, dependency-free URL shortener HTTP server backed by SQLite.


BASE62 = string.ascii_letters + string.digits  # 52 + 10 = 62


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def valid_url(url: str) -> bool:
    # Very light URL validation: must start with http:// or https:// and have at least one dot
    return bool(re.match(r"^(https?://)[^\s/$.?#].[^\s]*$", url))


def init_db(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            PRAGMA journal_mode=WAL;
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS short_urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                url TEXT NOT NULL,
                created_at TEXT NOT NULL,
                clicks INTEGER NOT NULL DEFAULT 0,
                last_accessed_at TEXT
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_id INTEGER NOT NULL,
                ts TEXT NOT NULL,
                ip TEXT,
                user_agent TEXT,
                referrer TEXT,
                FOREIGN KEY(short_id) REFERENCES short_urls(id)
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def get_db(db_path: str) -> sqlite3.Connection:
    # Open a new connection per call; safe for threading in tests
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


class RateLimiter:
    """Simple in-memory sliding-window rate limiter per (ip, key)."""

    def __init__(self):
        self._buckets: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, ip: str, key: str, limit: int, window_s: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_s
        k = (ip, key)
        with self._lock:
            q = self._buckets[k]
            # drop old
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True


class URLShortenerHandler(BaseHTTPRequestHandler):
    server_version = "PyURLShortener/1.0"

    # Injected via server
    db_path: str
    base_url: str
    rate_limiter: RateLimiter

    def _json(self, code: int, obj: dict, headers: Optional[dict] = None):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _text(self, code: int, text: str, headers: Optional[dict] = None):
        data = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        # Quieter logs during tests
        return

    def do_POST(self):
        if self.path == "/api/shorten":
            self._handle_shorten()
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_GET(self):
        if self.path == "/health":
            self._text(HTTPStatus.OK, "ok")
            return
        if self.path.startswith("/api/info/"):
            code = self.path[len("/api/info/"):]
            self._handle_info(code)
            return
        # Redirect handler at "/<code>"
        m = re.match(r"^/([A-Za-z0-9]{4,32})$", self.path)
        if m:
            code = m.group(1)
            self._handle_redirect(code)
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def _client_ip(self) -> str:
        # Honor X-Forwarded-For first IP if present, else peername
        xff = self.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
        return self.client_address[0]

    def _read_json(self) -> Tuple[Optional[dict], Optional[str]]:
        try:
            l = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(l) if l > 0 else b""
            if not body:
                return None, "empty_body"
            return json.loads(body.decode("utf-8")), None
        except Exception:
            return None, "invalid_json"

    def _generate_code_and_insert(self, url: str) -> Tuple[str, int]:
        # Attempt to insert with random code; retry on collision
        # Using a UNIQUE constraint on code ensures safety
        for length in (8, 9, 10):  # increase length if extremely unlucky
            for _ in range(10_000):
                code = "".join(secrets.choice(BASE62) for _ in range(length))
                conn = get_db(self.db_path)
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO short_urls(code, url, created_at) VALUES (?, ?, ?)",
                        (code, url, utc_now_iso()),
                    )
                    conn.commit()
                    short_id = cur.lastrowid
                    return code, short_id
                except sqlite3.IntegrityError:
                    # code collision, retry
                    pass
                finally:
                    conn.close()
        raise RuntimeError("Failed to generate unique short code after many attempts")

    def _handle_shorten(self):
        ip = self._client_ip()
        if not self.server.rate_limiter.allow(ip, "shorten", limit=5, window_s=60):
            self._json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "rate_limited"})
            return

        payload, err = self._read_json()
        if err:
            self._json(HTTPStatus.BAD_REQUEST, {"error": err})
            return
        url = payload.get("url") if isinstance(payload, dict) else None
        if not isinstance(url, str) or not valid_url(url):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_url"})
            return

        code, _sid = self._generate_code_and_insert(url)
        short_url = f"{self.server.base_url}/{code}"
        self._json(HTTPStatus.CREATED, {"code": code, "short_url": short_url, "url": url})

    def _handle_redirect(self, code: str):
        ip = self._client_ip()
        if not self.server.rate_limiter.allow(ip, "redirect", limit=120, window_s=60):
            self._text(HTTPStatus.TOO_MANY_REQUESTS, "rate_limited")
            return

        conn = get_db(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, url FROM short_urls WHERE code = ?", (code,))
            row = cur.fetchone()
            if not row:
                self._json(HTTPStatus.NOT_FOUND, {"error": "unknown_code"})
                return
            short_id, url = row
            # record click atomically-ish
            ua = self.headers.get("User-Agent")
            ref = self.headers.get("Referer")
            now_iso = utc_now_iso()
            cur.execute(
                "INSERT INTO clicks(short_id, ts, ip, user_agent, referrer) VALUES (?, ?, ?, ?, ?)",
                (short_id, now_iso, ip, ua, ref),
            )
            cur.execute(
                "UPDATE short_urls SET clicks = clicks + 1, last_accessed_at = ? WHERE id = ?",
                (now_iso, short_id),
            )
            conn.commit()
        finally:
            conn.close()

        # Send redirect
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", url)
        self.end_headers()

    def _handle_info(self, code: str):
        conn = get_db(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, url, created_at, clicks, last_accessed_at FROM short_urls WHERE code = ?",
                (code,),
            )
            row = cur.fetchone()
            if not row:
                self._json(HTTPStatus.NOT_FOUND, {"error": "unknown_code"})
                return
            sid, url, created_at, clicks, last_accessed = row
            cur.execute("SELECT COUNT(*), MAX(ts) FROM clicks WHERE short_id = ?", (sid,))
            c_row = cur.fetchone() or (0, None)
            click_count, last_click = c_row
            self._json(
                HTTPStatus.OK,
                {
                    "code": code,
                    "url": url,
                    "created_at": created_at,
                    "clicks": int(clicks),
                    "last_accessed_at": last_accessed,
                    "click_count": int(click_count),
                    "last_click_at": last_click,
                },
            )
        finally:
            conn.close()


class URLShortenerServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, db_path: str, base_url: str):
        super().__init__(server_address, RequestHandlerClass)
        # attach config
        self.db_path = db_path
        self.base_url = base_url.rstrip("/")
        self.rate_limiter = RateLimiter()
        # make available on handler
        RequestHandlerClass.db_path = self.db_path
        RequestHandlerClass.base_url = self.base_url
        RequestHandlerClass.rate_limiter = self.rate_limiter


def run(host: str = "127.0.0.1", port: int = 8000, db_path: str = "./data.sqlite"):
    init_db(db_path)
    base_url = f"http://{host}:{port}"
    httpd = URLShortenerServer((host, port), URLShortenerHandler, db_path=db_path, base_url=base_url)
    print(f"Serving on {base_url}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def run_in_thread(port: int = 0, db_path: str = ":memory:") -> Tuple[URLShortenerServer, threading.Thread, int]:
    """
    Helper for tests: start the server on an ephemeral port in a background thread.
    Returns (server, thread, actual_port)
    """
    # Bind to get an ephemeral port if 0
    host = "127.0.0.1"
    # If using :memory:, each connection would be a new empty DB. Use a temp file instead in tests.
    init_db(db_path)
    # Create a temporary socket to find free port when port==0
    s = socket.socket()
    s.bind((host, port))
    actual_port = s.getsockname()[1]
    s.close()
    base_url = f"http://{host}:{actual_port}"
    httpd = URLShortenerServer((host, actual_port), URLShortenerHandler, db_path=db_path, base_url=base_url)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, t, actual_port


if __name__ == "__main__":
    run()
