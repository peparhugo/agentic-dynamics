import pytest
import aiosqlite
from httpx import AsyncClient, ASGITransport
from url_shortener.main import app
from url_shortener.utils import generate_code, validate_url, CODE_LENGTH

DB_PATH = ":memory:"


@pytest.fixture(autouse=True)
async def setup_db():
    from url_shortener import database as db_mod

    db_mod.DB_PATH = DB_PATH
    app.state.db = await db_mod.get_db()
    yield
    await app.state.db.close()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestCodeGeneration:
    def test_generate_code_default_length(self):
        code = generate_code()
        assert len(code) == CODE_LENGTH
        assert all(c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" for c in code)

    def test_generate_code_custom_length(self):
        for length in [5, 8, 10]:
            code = generate_code(length)
            assert len(code) == length

    def test_codes_are_unique(self):
        codes = {generate_code() for _ in range(100)}
        assert len(codes) == 100

    def test_codes_use_full_alphabet(self):
        codes = [generate_code() for _ in range(500)]
        chars = set("".join(codes))
        assert len(chars) >= 50


class TestURLValidation:
    def test_valid_http_url(self):
        assert validate_url("http://example.com")

    def test_valid_https_url(self):
        assert validate_url("https://example.com/path?q=1")

    def test_valid_url_with_port(self):
        assert validate_url("https://example.com:8080/path")

    def test_valid_localhost(self):
        assert validate_url("http://localhost:3000/api")

    def test_invalid_no_scheme(self):
        assert not validate_url("example.com")

    def test_invalid_empty(self):
        assert not validate_url("")

    def test_invalid_ftp(self):
        assert not validate_url("ftp://example.com")


class TestShortenAPI:
    @pytest.mark.anyio
    async def test_shorten_valid_url(self, client):
        resp = await client.post("/api/shorten", json={"url": "https://example.com"})
        assert resp.status_code == 201
        data = resp.json()
        assert "code" in data
        assert len(data["code"]) == CODE_LENGTH
        assert data["short_url"] == f"http://test/{data['code']}"
        assert data["original_url"] == "https://example.com"

    @pytest.mark.anyio
    async def test_shorten_invalid_url(self, client):
        resp = await client.post("/api/shorten", json={"url": "not-a-url"})
        assert resp.status_code == 400
        assert "Invalid URL" in resp.json()["detail"]

    @pytest.mark.anyio
    async def test_shorten_empty_str(self, client):
        resp = await client.post("/api/shorten", json={"url": ""})
        assert resp.status_code == 400


class TestRedirect:
    @pytest.mark.anyio
    async def test_redirect_to_original(self, client):
        create = await client.post(
            "/api/shorten", json={"url": "https://example.com/target"}
        )
        code = create.json()["code"]

        resp = await client.get(f"/{code}", follow_redirects=False)
        assert resp.status_code == 301
        assert resp.headers["location"] == "https://example.com/target"

    @pytest.mark.anyio
    async def test_redirect_not_found(self, client):
        resp = await client.get("/nonexistent")
        assert resp.status_code == 404


class TestAnalytics:
    @pytest.mark.anyio
    async def test_stats_tracks_clicks(self, client):
        create = await client.post(
            "/api/shorten", json={"url": "https://example.com/stats-test"}
        )
        code = create.json()["code"]

        await client.get(f"/{code}", follow_redirects=False)

        resp = await client.get(f"/api/stats/{code}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["clicks"] == 1
        assert data["total_visits"] == 1

    @pytest.mark.anyio
    async def test_stats_not_found(self, client):
        resp = await client.get("/api/stats/nonexistent")
        assert resp.status_code == 404


class TestListURLs:
    @pytest.mark.anyio
    async def test_list_empty(self, client):
        resp = await client.get("/api/urls")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.anyio
    async def test_list_with_urls(self, client):
        await client.post("/api/shorten", json={"url": "https://a.com"})
        await client.post("/api/shorten", json={"url": "https://b.com"})

        resp = await client.get("/api/urls")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert all(k in data[0] for k in ("code", "url", "created_at", "clicks"))


class TestDeleteURL:
    @pytest.mark.anyio
    async def test_delete_existing(self, client):
        create = await client.post("/api/shorten", json={"url": "https://example.com"})
        code = create.json()["code"]

        resp = await client.delete(f"/api/urls/{code}")
        assert resp.status_code == 200

        get_resp = await client.get(f"/{code}", follow_redirects=False)
        assert get_resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_not_found(self, client):
        resp = await client.delete("/api/urls/nonexistent")
        assert resp.status_code == 404
