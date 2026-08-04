import json
import os
import sys
import tempfile
import time
from pathlib import Path
from urllib import request, error

import pytest

# Ensure repo root on path to import app.py
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_call(method: str, url: str, data: dict | None = None, headers: dict | None = None, follow_redirects: bool = False):
    hdrs = {"User-Agent": "pytest-client/1.0"}
    if headers:
        hdrs.update(headers)
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = request.Request(url, data=body, method=method, headers=hdrs)
    opener = request.build_opener() if follow_redirects else request.build_opener(NoRedirect)
    try:
        resp = opener.open(req, timeout=5)
        status = resp.getcode()
        raw = resp.read()
        return status, dict(resp.headers.items()), raw
    except error.HTTPError as e:
        raw = e.read()
        return e.code, dict(e.headers.items()), raw


@pytest.fixture()
def server():
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "data.sqlite")
        httpd, t, port = app.run_in_thread(port=0, db_path=db_path)
        base = f"http://127.0.0.1:{port}"
        # Wait briefly for server to start
        for _ in range(50):
            try:
                s, _, _ = http_call("GET", f"{base}/health")
                if s == 200:
                    break
            except Exception:
                pass
            time.sleep(0.02)
        yield {"httpd": httpd, "thread": t, "port": port, "base": base, "db_path": db_path}
        httpd.shutdown()
        t.join(timeout=2)


def test_shorten_redirect_and_info(server):
    base = server["base"]
    # Create a short URL
    status, headers, body = http_call("POST", f"{base}/api/shorten", {"url": "https://example.com/path"})
    assert status == 201, (status, body)
    data = json.loads(body)
    assert "code" in data and "short_url" in data
    code = data["code"]

    # Redirect should 302
    status, headers, body = http_call("GET", f"{base}/{code}")
    assert status == 302
    assert headers.get("Location") == "https://example.com/path"

    # Second click
    status, headers, body = http_call("GET", f"{base}/{code}")
    assert status == 302

    # Info should reflect clicks
    status, headers, body = http_call("GET", f"{base}/api/info/{code}")
    assert status == 200
    info = json.loads(body)
    assert info["url"] == "https://example.com/path"
    # clicks stored and click_count from clicks table should both be 2
    assert info["clicks"] == 2
    assert info["click_count"] == 2
    assert info["last_accessed_at"] is not None


def test_invalid_url_rejected(server):
    base = server["base"]
    status, headers, body = http_call("POST", f"{base}/api/shorten", {"url": "not-a-url"})
    assert status == 400
    err = json.loads(body)
    assert err["error"] == "invalid_url"


def test_rate_limit_shorten(server):
    base = server["base"]
    # Allow 5 per minute
    for i in range(5):
        status, _, _ = http_call("POST", f"{base}/api/shorten", {"url": f"https://example.com/{i}"})
        assert status == 201
    status, headers, body = http_call("POST", f"{base}/api/shorten", {"url": "https://example.com/overflow"})
    assert status == 429


def test_collision_retry(server, monkeypatch):
    base = server["base"]
    db_path = server["db_path"]
    # Pre-insert a known code "AAAAAAAA"
    conn = app.get_db(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO short_urls(code, url, created_at) VALUES (?, ?, ?)",
            ("AAAAAAAA", "https://already.example/", app.utc_now_iso()),
        )
        conn.commit()
    finally:
        conn.close()

    # Patch secrets.choice to force first attempt to generate AAAAAAAA and then BBBBBBBB
    calls = {"n": 0}

    def fake_choice(_seq):
        calls["n"] += 1
        # First 8 calls -> 'A', next 8 -> 'B', then default to 'C'
        if calls["n"] <= 8:
            return "A"
        elif calls["n"] <= 16:
            return "B"
        return "C"

    monkeypatch.setattr(app.secrets, "choice", fake_choice)

    status, headers, body = http_call("POST", f"{base}/api/shorten", {"url": "https://new.example/"})
    assert status == 201
    data = json.loads(body)
    # Should not be the colliding code
    assert data["code"] != "AAAAAAAA"


def test_rate_limit_redirect(server):
    base = server["base"]
    # Create once
    status, _, body = http_call("POST", f"{base}/api/shorten", {"url": "https://example.com/rl"})
    assert status == 201
    code = json.loads(body)["code"]
    # Find the first 429 position; expect it on the 121st request
    success = 0
    first_429_at = None
    for i in range(130):
        s, _, _ = http_call("GET", f"{base}/{code}")
        if s == 302:
            success += 1
        elif s == 429 and first_429_at is None:
            first_429_at = i + 1  # 1-based count
            break
        else:
            pytest.fail(f"Unexpected status {s}")
    assert first_429_at is not None, "Did not hit rate limit within 130 requests"
    assert success == 120, f"Expected 120 successes before 429, got {success}"
    assert first_429_at == 121, f"Expected 429 on 121st request, got {first_429_at}"
