from app import create_app
from app.config import TestConfig


def test_rate_limit_enforced():
    app = create_app(TestConfig)
    app.config["RATELIMIT_ENABLED"] = True
    app.config["RATELIMIT_DEFAULT"] = "3 per hour"
    with app.app_context(), app.test_client() as client:
        from app import db as _db
        _db.create_all()
        client.post("/api/v1/register", json={
            "username": "rluser", "email": "rl@example.com", "password": "password123"
        })
        resp = client.post("/api/v1/login", json={
            "email": "rl@example.com", "password": "password123"
        })
        token = resp.get_json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        # login has a 10/hour limit, so 3 should pass. Items use default 3/hour.
        passed = 0
        for _ in range(10):
            r = client.get("/api/v1/items", headers=headers)
            if r.status_code == 429:
                break
            passed += 1
        assert passed >= 1
        assert any(r.status_code == 429 for _ in range(1))
    with app.app_context():
        _db.session.remove()
        _db.drop_all()
