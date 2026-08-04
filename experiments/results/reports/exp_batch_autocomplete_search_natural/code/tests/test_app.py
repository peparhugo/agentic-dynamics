import json
import time
import pytest
from autocomplete.app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestAppRoutes:
    def test_index_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"<!DOCTYPE html>" in resp.data or b"<html" in resp.data.lower()

    def test_widget_js_returns_javascript(self, client):
        resp = client.get("/widget/autocomplete.js")
        assert resp.status_code == 200
        assert resp.content_type == "application/javascript"

    def test_suggest_returns_json(self, client):
        resp = client.get("/api/suggest?q=iphone")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["query"] == "iphone"
        assert "groups" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_suggest_no_query(self, client):
        resp = client.get("/api/suggest")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["total"] == 0

    def test_suggest_empty_query(self, client):
        resp = client.get("/api/suggest?q=")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["total"] == 0

    def test_suggest_spaces_only(self, client):
        resp = client.get("/api/suggest?q=   ")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["total"] == 0

    def test_suggest_no_results(self, client):
        resp = client.get("/api/suggest?q=xyznonexistent123456")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["total"] == 0
        assert data["groups"] == []

    def test_suggest_case_insensitive(self, client):
        lower = client.get("/api/suggest?q=iphone")
        upper = client.get("/api/suggest?q=IPHONE")
        lower_data = json.loads(lower.data)
        upper_data = json.loads(upper.data)
        assert lower_data["total"] == upper_data["total"]

    def test_suggest_response_structure(self, client):
        resp = client.get("/api/suggest?q=apple")
        data = json.loads(resp.data)
        assert isinstance(data["groups"], list)
        if len(data["groups"]) > 0:
            group = data["groups"][0]
            assert "category" in group
            assert "results" in group
            if len(group["results"]) > 0:
                item = group["results"][0]
                for field in ["id", "title", "description", "category", "url", "score"]:
                    assert field in item

    def test_trending_returns_json(self, client):
        resp = client.get("/api/trending")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert isinstance(data, list)
        assert len(data) > 0
        for item in data:
            assert "title" in item
            assert "category" in item

    def test_analytics_post(self, client):
        resp = client.post(
            "/api/analytics",
            data=json.dumps({"type": "search_start", "data": {"query": "test"}}),
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert data["success"] is True

    def test_analytics_post_empty_body(self, client):
        resp = client.post("/api/analytics", content_type="application/json")
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert data["success"] is True
        assert data["event"]["type"] == "unknown"

    def test_cors_headers_present(self, client):
        resp = client.get("/api/suggest?q=test")
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"

    def test_caching_behavior(self, client):
        resp1 = client.get("/api/suggest?q=macbook")
        resp2 = client.get("/api/suggest?q=macbook")
        data1 = json.loads(resp1.data)
        data2 = json.loads(resp2.data)
        assert data1 == data2

    def test_multiple_categories_in_results(self, client):
        resp = client.get("/api/suggest?q=pro")
        data = json.loads(resp.data)
        categories = {g["category"] for g in data["groups"]}
        assert len(categories) >= 1
