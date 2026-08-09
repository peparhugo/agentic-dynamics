import pytest
import httpx
import os
from httpx import ASGITransport
from app.main import app
from app.database import get_db, init_db, get_url, DB_PATH
from app.shortcode import generate_short_code, ALPHABET, CODE_LENGTH
from app.rate_limiter import SlidingWindowRateLimiter

TEST_DB = "test_urls.db"


@pytest.fixture
def test_db_path():
    return TEST_DB


@pytest.fixture(autouse=True)
def use_test_db(monkeypatch):
    monkeypatch.setattr("app.database.DB_PATH", TEST_DB)
    yield
    try:
        os.remove(TEST_DB)
    except FileNotFoundError:
        pass


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


class TestShortCodeGeneration:
    def test_code_length_is_correct(self):
        code = generate_short_code()
        assert len(code) == CODE_LENGTH

    def test_characters_are_from_alphabet(self):
        code = generate_short_code()
        for ch in code:
            assert ch in ALPHABET

    def test_codes_are_unique_over_many_generations(self):
        codes = {generate_short_code() for _ in range(1000)}
        assert len(codes) == 1000

    def test_url_safe_characters(self):
        code = generate_short_code()
        assert "/" not in code
        assert "+" not in code
        assert "=" not in code


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_allows_requests_under_limit(self):
        limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60.0)
        for _ in range(5):
            assert await limiter.is_allowed("127.0.0.1") is True

    @pytest.mark.asyncio
    async def test_blocks_requests_over_limit(self):
        limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60.0)
        for _ in range(3):
            assert await limiter.is_allowed("127.0.0.1") is True
        assert await limiter.is_allowed("127.0.0.1") is False

    @pytest.mark.asyncio
    async def test_separate_keys_have_separate_buckets(self):
        limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60.0)
        assert await limiter.is_allowed("1.1.1.1")
        assert await limiter.is_allowed("1.1.1.1")
        assert not await limiter.is_allowed("1.1.1.1")
        assert await limiter.is_allowed("2.2.2.2")


class TestShortenAPI:
    @pytest.mark.asyncio
    async def test_shorten_valid_url(self, client):
        resp = await client.post("/api/shorten", json={"url": "https://example.com"})
        assert resp.status_code == 201
        data = resp.json()
        assert "short_code" in data
        assert "short_url" in data
        assert data["original_url"] == "https://example.com/"
        assert len(data["short_code"]) == CODE_LENGTH

    @pytest.mark.asyncio
    async def test_shorten_invalid_url(self, client):
        resp = await client.post("/api/shorten", json={"url": "not-a-valid-url"})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_shorten_missing_body(self, client):
        resp = await client.post("/api/shorten", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_different_urls_get_different_codes(self, client):
        resp1 = await client.post("/api/shorten", json={"url": "https://example.com"})
        resp2 = await client.post("/api/shorten", json={"url": "https://example.org"})
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["short_code"] != resp2.json()["short_code"]

    @pytest.mark.asyncio
    async def test_same_url_gets_different_codes(self, client):
        codes = set()
        for _ in range(5):
            resp = await client.post("/api/shorten", json={"url": "https://example.com"})
            assert resp.status_code == 201
            codes.add(resp.json()["short_code"])
        assert len(codes) == 5

    @pytest.mark.asyncio
    async def test_short_url_has_correct_format(self, client):
        resp = await client.post("/api/shorten", json={"url": "https://example.com"})
        data = resp.json()
        expected = f"http://testserver/{data['short_code']}"
        assert data["short_url"] == expected

    @pytest.mark.asyncio
    async def test_empty_url_rejected(self, client):
        resp = await client.post("/api/shorten", json={"url": ""})
        assert resp.status_code == 422


class TestRedirectAPI:
    @pytest.mark.asyncio
    async def test_redirect_valid_code(self, client):
        resp = await client.post("/api/shorten", json={"url": "https://example.com"})
        code = resp.json()["short_code"]

        redirect_resp = await client.get(f"/{code}", follow_redirects=False)
        assert redirect_resp.status_code == 302
        assert redirect_resp.headers["location"] == "https://example.com/"

    @pytest.mark.asyncio
    async def test_redirect_nonexistent_code(self, client):
        resp = await client.get("/nonexist", follow_redirects=False)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_redirect_increments_click_count(self, client):
        resp = await client.post("/api/shorten", json={"url": "https://example.com"})
        code = resp.json()["short_code"]

        for _ in range(3):
            await client.get(f"/{code}", follow_redirects=False)

        stats_resp = await client.get(f"/api/stats/{code}")
        assert stats_resp.json()["click_count"] == 3

    @pytest.mark.asyncio
    async def test_redirect_sets_last_clicked_at(self, client):
        resp = await client.post("/api/shorten", json={"url": "https://example.com"})
        code = resp.json()["short_code"]

        await client.get(f"/{code}", follow_redirects=False)

        stats_resp = await client.get(f"/api/stats/{code}")
        assert stats_resp.json()["last_clicked_at"] is not None


class TestStatsAPI:
    @pytest.mark.asyncio
    async def test_stats_existing_code(self, client):
        resp = await client.post("/api/shorten", json={"url": "https://example.com"})
        code = resp.json()["short_code"]

        stats_resp = await client.get(f"/api/stats/{code}")
        assert stats_resp.status_code == 200
        data = stats_resp.json()
        assert data["short_code"] == code
        assert data["original_url"] == "https://example.com/"
        assert data["click_count"] == 0
        assert data["last_clicked_at"] is None
        assert data["created_at"] is not None

    @pytest.mark.asyncio
    async def test_stats_nonexistent_code(self, client):
        resp = await client.get("/api/stats/doesnotexist")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_stats_with_clicks(self, client):
        resp = await client.post("/api/shorten", json={"url": "https://example.com"})
        code = resp.json()["short_code"]

        for _ in range(5):
            await client.get(f"/{code}", follow_redirects=False)

        stats = await client.get(f"/api/stats/{code}")
        assert stats.json()["click_count"] == 5

    @pytest.mark.asyncio
    async def test_stats_click_count_is_int(self, client):
        resp = await client.post("/api/shorten", json={"url": "https://example.com"})
        code = resp.json()["short_code"]

        stats = await client.get(f"/api/stats/{code}")
        assert isinstance(stats.json()["click_count"], int)


class TestRateLimitingAPI:
    @pytest.mark.asyncio
    async def test_rate_limit_enforced(self, client):
        for _ in range(10):
            resp = await client.post("/api/shorten", json={"url": "https://example.com"})
            assert resp.status_code == 201

        resp = await client.post("/api/shorten", json={"url": "https://example.com"})
        assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_response_message(self, client):
        for _ in range(10):
            await client.post("/api/shorten", json={"url": "https://example.com"})

        resp = await client.post("/api/shorten", json={"url": "https://example.com"})
        assert resp.status_code == 429
        assert "Too many requests" in resp.json()["detail"]


class TestDatabase:
    @pytest.mark.asyncio
    async def test_urls_table_schema(self, test_db_path):
        from app.database import get_db, init_db
        db = await get_db()
        try:
            await init_db(db)
            cursor = await db.execute("PRAGMA table_info(urls)")
            columns = await cursor.fetchall()
            col_names = [col[1] for col in columns]
            assert "short_code" in col_names
            assert "original_url" in col_names
            assert "created_at" in col_names
            assert "click_count" in col_names
            assert "last_clicked_at" in col_names
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_insert_and_retrieve(self, test_db_path):
        from app.database import get_db, init_db, insert_url, get_url
        db = await get_db()
        try:
            await init_db(db)
            await insert_url(db, "abc1234", "https://example.com")
            row = await get_url(db, "abc1234")
            assert row is not None
            assert row["short_code"] == "abc1234"
            assert row["original_url"] == "https://example.com"
            assert row["click_count"] == 0
            assert row["last_clicked_at"] is None
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_increment_click_updates_count_and_timestamp(self, test_db_path):
        from app.database import get_db, init_db, insert_url, get_url, increment_click
        db = await get_db()
        try:
            await init_db(db)
            await insert_url(db, "xyz9999", "https://example.com")
            await increment_click(db, "xyz9999")
            row = await get_url(db, "xyz9999")
            assert row["click_count"] == 1
            assert row["last_clicked_at"] is not None
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, test_db_path):
        from app.database import get_db, init_db, get_url
        db = await get_db()
        try:
            await init_db(db)
            row = await get_url(db, "nope000")
            assert row is None
        finally:
            await db.close()


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_long_url_handled(self, client):
        long_url = "https://example.com/" + "a" * 2000
        resp = await client.post("/api/shorten", json={"url": long_url})
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_url_with_query_params(self, client):
        resp = await client.post(
            "/api/shorten",
            json={"url": "https://example.com/search?q=hello&page=2"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "search?q=hello" in data["original_url"]

    @pytest.mark.asyncio
    async def test_url_with_fragment(self, client):
        resp = await client.post(
            "/api/shorten",
            json={"url": "https://example.com/page#section"},
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_http_url_accepted(self, client):
        resp = await client.post("/api/shorten", json={"url": "http://example.com"})
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_concurrent_shorten_requests(self, client):
        import asyncio

        async def create():
            return await client.post("/api/shorten", json={"url": "https://example.com"})

        results = await asyncio.gather(*[create() for _ in range(5)])
        codes = [r.json()["short_code"] for r in results]
        assert len(set(codes)) == 5
