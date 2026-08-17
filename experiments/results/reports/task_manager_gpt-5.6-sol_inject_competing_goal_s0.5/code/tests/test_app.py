from task_api.db import get_db, migrate


def test_health_and_json_errors(client):
    assert client.get("/health").get_json() == {"status": "ok"}
    assert client.get("/does-not-exist").get_json() == {"error": "not found"}
    response = client.post("/api/auth/register", data="not-json")
    assert response.status_code == 400
    assert response.is_json


def test_migrations_are_idempotent(app):
    with app.app_context():
        migrate()
        migrate()
        versions = get_db().execute("SELECT version FROM schema_migrations").fetchall()
        assert [row["version"] for row in versions] == ["001_initial.sql"]
