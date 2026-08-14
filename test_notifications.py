from tasks import send_notification_email


def register(client, username, password):
    return client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def login(client, username, password):
    return client.post(
        "/auth/login", json={"username": username, "password": password}
    )


def auth_headers(client, username="alice", password="secret"):
    register(client, username, password)
    resp = login(client, username, password)
    return {"Authorization": f"Bearer {resp.get_json()['token']}"}


def create_task(client, title, username="alice", password="secret"):
    return client.post(
        "/tasks", json={"title": title}, headers=auth_headers(client, username, password)
    )


# ── Notification trigger logic ─────────────────────────────────


def test_send_notification_email_task(capsys):
    result = send_notification_email.run("alice@example.com", "Buy milk")
    assert result["user_email"] == "alice@example.com"
    assert result["task_title"] == "Buy milk"
    out = capsys.readouterr().out
    assert "alice@example.com" in out
    assert "Buy milk" in out


def test_completing_task_triggers_notification(client, monkeypatch):
    dispatched = {}
    monkeypatch.setattr(
        "app.dispatch_completion_email",
        lambda email, title: dispatched.update({"email": email, "title": title}),
    )
    created = create_task(client, "Ship feature").get_json()
    resp = client.put(
        f"/tasks/{created['id']}",
        json={"status": "completed"},
        headers=auth_headers(client),
    )
    assert resp.status_code == 200
    assert dispatched.get("email") == "alice"
    assert dispatched.get("title") == "Ship feature"


def test_no_notification_for_non_completed_status(client, monkeypatch):
    dispatched = {"count": 0}
    monkeypatch.setattr(
        "app.dispatch_completion_email",
        lambda email, title: dispatched.update({"count": dispatched["count"] + 1}),
    )
    created = create_task(client, "Do the dishes").get_json()
    client.put(
        f"/tasks/{created['id']}",
        json={"status": "in_progress"},
        headers=auth_headers(client),
    )
    assert dispatched["count"] == 0


def test_no_duplicate_notification_when_already_completed(client, monkeypatch):
    dispatched = {"count": 0}
    monkeypatch.setattr(
        "app.dispatch_completion_email",
        lambda email, title: dispatched.update({"count": dispatched["count"] + 1}),
    )
    created = create_task(client, "Deploy app").get_json()
    headers = auth_headers(client)
    client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
    )
    client.put(
        f"/tasks/{created['id']}", json={"status": "completed"}, headers=headers
    )
    assert dispatched["count"] == 1
