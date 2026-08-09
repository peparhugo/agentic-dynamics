import asyncio
import os
import time

import pytest
from httpx import ASGITransport, AsyncClient

os.environ["DB_PATH"] = ":memory:"

from urlshortener.main import app
from urlshortener.storage import DB_PATH, check_code_exists, init_db


@pytest.fixture(autouse=True)
async def reset_db():
    import urlshortener.storage as s

    old = DB_PATH
    s.DB_PATH = ":memory:"
    await init_db()
    yield
    s.DB_PATH = old


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_shorten_url_creates_short_link(client):
    resp = await client.post("/shorten", json={"url": "https://example.com"})
    assert resp.status_code == 201
    data = resp.json()
    assert "code" in data
    assert len(data["code"]) == 8
    assert data["original_url"] == "https://example.com"
    assert data["short_url"] == f"http://test/{data['code']}"


@pytest.mark.asyncio
async def test_shorten_url_requires_http_url(client):
    resp = await client.post("/shorten", json={"url": "not-a-url"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_shorten_url_rejects_empty(client):
    resp = await client.post("/shorten", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_shorten_url_rejects_self_referencing(client):
    resp = await client.post("/shorten", json={"url": "http://test/somepath"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_redirect_returns_302(client):
    resp = await client.post("/shorten", json={"url": "https://example.com"})
    code = resp.json()["code"]

    redirect_resp = await client.get(f"/{code}", follow_redirects=False)
    assert redirect_resp.status_code == 302
    assert redirect_resp.headers["location"] == "https://example.com"


@pytest.mark.asyncio
async def test_redirect_unknown_code_returns_404(client):
    resp = await client.get("/nonexistent", follow_redirects=False)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stats_returns_click_data(client):
    resp = await client.post("/shorten", json={"url": "https://example.com"})
    code = resp.json()["code"]

    await client.get(f"/{code}", follow_redirects=False)
    await asyncio.sleep(0.1)

    stats_resp = await client.get(f"/{code}/stats")
    assert stats_resp.status_code == 200
    data = stats_resp.json()
    assert data["code"] == code
    assert data["original_url"] == "https://example.com"
    assert data["total_clicks"] >= 1


@pytest.mark.asyncio
async def test_stats_increments_on_multiple_clicks(client):
    resp = await client.post("/shorten", json={"url": "https://example.com"})
    code = resp.json()["code"]

    for _ in range(3):
        await client.get(f"/{code}", follow_redirects=False)
    await asyncio.sleep(0.1)

    stats_resp = await client.get(f"/{code}/stats")
    data = stats_resp.json()
    assert data["total_clicks"] >= 3


@pytest.mark.asyncio
async def test_stats_unknown_code_returns_404(client):
    resp = await client.get("/nonexistent/stats")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_code_collision_resistance(client):
    codes = set()
    for _ in range(20):
        resp = await client.post(
            "/shorten", json={"url": f"https://example.com/path/{_}"}
        )
        data = resp.json()
        assert data["code"] not in codes, f"Collision detected: {data['code']}"
        codes.add(data["code"])
    assert len(codes) == 20


@pytest.mark.asyncio
async def test_rate_limiting(client):
    import urlshortener.ratelimit as rl

    old_bucket = rl.bucket
    rl.bucket = type(rl.bucket)(rate=5.0, burst=3)

    for i in range(3):
        resp = await client.post(
            "/shorten", json={"url": f"https://example.com/path/{i}"}
        )
        assert resp.status_code == 201, f"Request {i} should succeed"

    resp = await client.post(
        "/shorten", json={"url": "https://example.com/blocked"}
    )
    assert resp.status_code == 429

    rl.bucket = old_bucket


@pytest.mark.asyncio
async def test_shorten_preserves_url_with_path_and_query(client):
    resp = await client.post(
        "/shorten",
        json={"url": "https://example.com/path/to/page?q=search&lang=en"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert (
        data["original_url"]
        == "https://example.com/path/to/page?q=search&lang=en"
    )

    redirect = await client.get(f"/{data['code']}", follow_redirects=False)
    assert (
        redirect.headers["location"]
        == "https://example.com/path/to/page?q=search&lang=en"
    )


@pytest.mark.asyncio
async def test_code_generation_uses_url_safe_chars():
    from urlshortener.codegen import ALPHABET, generate_code

    for _ in range(100):
        code = generate_code()
        assert len(code) == 8
        assert all(c in ALPHABET for c in code)


@pytest.mark.asyncio
async def test_token_bucket_algorithm():
    from urlshortener.ratelimit import TokenBucket

    tb = TokenBucket(rate=2.0, burst=5)
    key = "test_ip"

    assert all(tb.consume(key) for _ in range(5))
    assert not tb.consume(key)

    time.sleep(0.6)
    assert tb.consume(key)
    assert not tb.consume(key)


@pytest.mark.asyncio
async def test_concurrent_shorten_requests(client):
    async def shorten(i: int):
        resp = await client.post(
            "/shorten", json={"url": f"https://example.com/path/{i}"}
        )
        return resp.status_code, resp.json()["code"]

    results = await asyncio.gather(*[shorten(i) for i in range(10)])
    codes = [code for status, code in results]
    assert all(s == 201 for s, _ in results)
    assert len(set(codes)) == len(codes), "Duplicate codes detected"


@pytest.mark.asyncio
async def test_click_analytics_daily_breakdown(client):
    resp = await client.post("/shorten", json={"url": "https://example.com"})
    code = resp.json()["code"]

    await client.get(f"/{code}", follow_redirects=False)
    await asyncio.sleep(0.1)

    stats = await client.get(f"/{code}/stats")
    data = stats.json()
    assert len(data["daily_clicks"]) == 1
    assert data["daily_clicks"][0]["count"] >= 1


@pytest.mark.asyncio
async def test_click_analytics_tracks_referrer(client):
    resp = await client.post("/shorten", json={"url": "https://example.com"})
    code = resp.json()["code"]

    await client.get(
        f"/{code}",
        follow_redirects=False,
        headers={"Referer": "https://google.com"},
    )
    await asyncio.sleep(0.1)

    stats = await client.get(f"/{code}/stats")
    data = stats.json()
    referrers = [r["referrer"] for r in data["top_referrers"]]
    assert "https://google.com" in referrers
