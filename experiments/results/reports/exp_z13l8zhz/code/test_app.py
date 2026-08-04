import time

import pytest

from app import ALPHABET, BASE, _encode, app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestEncode:
    def test_zero(self):
        assert _encode(0) == ALPHABET[0]

    def test_encodes_correctly(self):
        assert _encode(1) == "1"
        assert _encode(BASE - 1) == ALPHABET[-1]
        assert _encode(BASE) == "10"

    def test_bijective_short(self):
        for n in [0, 1, 5, 61, 62, 100, 3844, 99999]:
            assert all(c in ALPHABET for c in _encode(n))


class TestShorten:
    def test_no_url(self, client):
        r = client.post("/shorten", json={})
        assert r.status_code == 400
        assert "url" in r.get_json()["error"]

    def test_bad_scheme(self, client):
        r = client.post("/shorten", json={"url": "ftp://x.com"})
        assert r.status_code == 400

    def test_creates_short_url(self, client):
        r = client.post("/shorten", json={"url": "https://example.com"})
        assert r.status_code == 201
        data = r.get_json()
        assert "short_id" in data
        assert data["url"] == "https://example.com"

    def test_with_ttl(self, client):
        r = client.post("/shorten", json={"url": "https://a.com", "ttl": 3600})
        assert r.status_code == 201
        assert r.get_json()["ttl"] == 3600

    def test_bad_ttl(self, client):
        r = client.post("/shorten", json={"url": "https://a.com", "ttl": "nope"})
        assert r.status_code == 400

    def test_negative_ttl(self, client):
        r = client.post("/shorten", json={"url": "https://a.com", "ttl": -1})
        assert r.status_code == 400

    def test_concurrent_ids_are_unique(self, client):
        ids = set()
        for _ in range(50):
            r = client.post("/shorten", json={"url": "https://x.com"})
            short_id = r.get_json()["short_id"]
            assert short_id not in ids
            ids.add(short_id)


class TestResolve:
    def test_redirects(self, client):
        r = client.post("/shorten", json={"url": "https://example.com/foo"})
        sid = r.get_json()["short_id"]
        r = client.get(f"/{sid}", follow_redirects=False)
        assert r.status_code == 302
        assert r.headers["Location"] == "https://example.com/foo"

    def test_not_found(self, client):
        r = client.get("/nonexistent")
        assert r.status_code == 404

    def test_expired(self, client):
        r = client.post("/shorten", json={"url": "https://a.com", "ttl": 0.01})
        sid = r.get_json()["short_id"]
        time.sleep(0.02)
        r = client.get(f"/{sid}")
        assert r.status_code == 410


class TestStats:
    def test_returns_stats(self, client):
        r = client.post("/shorten", json={"url": "https://b.com"})
        sid = r.get_json()["short_id"]
        client.get(f"/{sid}")
        client.get(f"/{sid}")
        r = client.get(f"/stats/{sid}")
        assert r.status_code == 200
        data = r.get_json()
        assert data["hits"] == 2
        assert data["url"] == "https://b.com"

    def test_stats_not_found(self, client):
        r = client.get("/stats/zzz")
        assert r.status_code == 404

    def test_created_timestamp(self, client):
        before = time.time()
        r = client.post("/shorten", json={"url": "https://c.com"})
        after = time.time()
        sid = r.get_json()["short_id"]
        created = client.get(f"/stats/{sid}").get_json()["created"]
        assert before <= created <= after
