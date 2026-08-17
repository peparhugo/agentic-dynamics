def test_health_check(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_users_list_requires_auth(client):
    resp = client.get("/api/users")
    assert resp.status_code == 401


def test_users_list(client, auth_headers, second_user):
    resp = client.get("/api/users", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    usernames = {item["username"] for item in body["items"]}
    assert {"alice", "bob"}.issubset(usernames)


def test_404_on_unknown_route(client):
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
    assert "error" in resp.get_json()
