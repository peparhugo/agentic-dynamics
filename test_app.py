import sqlite3
import xml.etree.ElementTree as ET

import app as task_app
import pytest
from werkzeug.security import check_password_hash


SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
TASK = "urn:tasks"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    monkeypatch.setattr(task_app, "JWT_SECRET", "test-secret")
    task_app.init_db()
    return task_app.app.test_client()


def soap_request(operation, fields=""):
    return f'<soap:Envelope xmlns:soap="{SOAP}" xmlns:t="{TASK}"><soap:Body><t:{operation}>{fields}</t:{operation}></soap:Body></soap:Envelope>'


def xml(response):
    return ET.fromstring(response.data)


def task_values(response):
    task = next(iter(xml(response).findall(".//Task")), None)
    return {child.tag: child.text for child in task}


def fault_text(response):
    return xml(response).findtext(f".//{{{SOAP}}}Fault/faultstring")


def register(client, username="alice", password="password", email=None):
    data = {"username": username, "password": password}
    if email is not None:
        data["email"] = email
    return client.post("/auth/register", json=data)


def token(client, username="alice", password="password"):
    register(client, username, password)
    return client.post("/auth/login", json={"username": username, "password": password}).get_json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_hashes_password(client):
    response = register(client)
    with task_app.get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", ("alice",)).fetchone()

    assert response.status_code == 201
    assert response.get_json() == {"id": 1, "username": "alice"}
    assert user["password_hash"] != "password"
    assert check_password_hash(user["password_hash"], "password")


def test_register_rejects_invalid_and_duplicate_users(client):
    invalid = client.post("/auth/register", json={"username": "alice"})
    register(client)
    duplicate = register(client)

    assert invalid.status_code == 400
    assert duplicate.status_code == 409


def test_login_returns_token_and_rejects_invalid_credentials(client):
    register(client)
    valid = client.post("/auth/login", json={"username": "alice", "password": "password"})
    invalid = client.post("/auth/login", json={"username": "alice", "password": "wrong"})

    assert valid.status_code == 200
    assert valid.get_json()["token"]
    assert invalid.status_code == 401


def test_tasks_require_valid_authentication(client):
    missing = client.post("/soap", data=soap_request("ListTasks"))
    invalid = client.post("/soap", data=soap_request("ListTasks"), headers=auth("invalid"))

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert fault_text(missing) == "authentication required"


def test_create_task_uses_pending_status(client):
    response = client.post("/soap", data=soap_request("CreateTask", "<title>Write tests</title>"), headers=auth(token(client)))

    assert response.status_code == 201
    assert response.content_type.startswith("text/xml")
    assert task_values(response)["title"] == "Write tests"
    assert task_values(response)["status"] == "pending"
    assert task_values(response)["created_at"]


def test_create_task_requires_title(client):
    response = client.post("/soap", data=soap_request("CreateTask"), headers=auth(token(client)))

    assert response.status_code == 400
    assert fault_text(response) == "title is required"


def test_list_tasks_is_newest_first_and_scoped_to_owner(client):
    alice_token = token(client)
    bob_token = token(client, "bob")
    client.post("/soap", data=soap_request("CreateTask", "<title>Older</title>"), headers=auth(alice_token))
    client.post("/soap", data=soap_request("CreateTask", "<title>Newer</title>"), headers=auth(alice_token))
    client.post("/soap", data=soap_request("CreateTask", "<title>Bob's</title>"), headers=auth(bob_token))

    response = client.post("/soap", data=soap_request("ListTasks"), headers=auth(alice_token))
    tasks = xml(response).findall(f".//{{{TASK}}}ListTasksResponse/Task")

    assert response.status_code == 200
    assert [task.findtext("title") for task in tasks] == ["Newer", "Older"]


def test_users_cannot_get_or_update_other_users_tasks(client):
    alice_token = token(client)
    created = client.post("/soap", data=soap_request("CreateTask", "<title>Private</title>"), headers=auth(alice_token))
    identifier = task_values(created)["id"]
    bob_token = token(client, "bob")

    fetched = client.post("/soap", data=soap_request("GetTask", f"<id>{identifier}</id>"), headers=auth(bob_token))
    updated = client.post("/soap", data=soap_request("UpdateTask", f"<id>{identifier}</id><status>complete</status>"), headers=auth(bob_token))

    assert fetched.status_code == 404
    assert updated.status_code == 404


def test_update_task_allows_partial_updates(client):
    access_token = token(client)
    created = client.post("/soap", data=soap_request("CreateTask", "<title>Draft</title>"), headers=auth(access_token))
    identifier = task_values(created)["id"]
    response = client.post("/soap", data=soap_request("UpdateTask", f"<id>{identifier}</id><status>complete</status>"), headers=auth(access_token))

    assert task_values(response)["title"] == "Draft"
    assert task_values(response)["status"] == "complete"


def test_completing_task_enqueues_notification(client, monkeypatch):
    register(client, email="alice@example.com")
    access_token = client.post("/auth/login", json={"username": "alice", "password": "password"}).get_json()["token"]
    created = client.post("/soap", data=soap_request("CreateTask", "<title>Ship feature</title>"), headers=auth(access_token))
    identifier = task_values(created)["id"]
    calls = []
    monkeypatch.setattr(task_app.send_notification_email, "delay", lambda *args: calls.append(args))

    response = client.post(
        "/soap",
        data=soap_request("UpdateTask", f"<id>{identifier}</id><status>completed</status>"),
        headers=auth(access_token),
    )

    assert response.status_code == 200
    assert calls == [("alice@example.com", "Ship feature")]


def test_notification_is_not_enqueued_when_task_is_already_completed(client, monkeypatch):
    register(client, email="alice@example.com")
    access_token = client.post("/auth/login", json={"username": "alice", "password": "password"}).get_json()["token"]
    created = client.post("/soap", data=soap_request("CreateTask", "<title>Ship feature</title>"), headers=auth(access_token))
    identifier = task_values(created)["id"]
    calls = []
    monkeypatch.setattr(task_app.send_notification_email, "delay", lambda *args: calls.append(args))
    body = soap_request("UpdateTask", f"<id>{identifier}</id><status>completed</status>")

    client.post("/soap", data=body, headers=auth(access_token))
    client.post("/soap", data=body, headers=auth(access_token))

    assert calls == [("alice@example.com", "Ship feature")]


def test_rejects_invalid_soap_requests(client):
    access_token = token(client)
    malformed = client.post("/soap", data="not xml", headers=auth(access_token))
    unknown = client.post("/soap", data=soap_request("DeleteTask"), headers=auth(access_token))

    assert malformed.status_code == 400
    assert fault_text(malformed) == "invalid SOAP XML"
    assert unknown.status_code == 400
    assert fault_text(unknown) == "unknown SOAP operation"


def test_init_db_migrates_existing_tasks_database(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)")
        conn.execute("INSERT INTO tasks VALUES (1, 'Legacy', 'pending', '2020-01-01T00:00:00+00:00')")
    monkeypatch.setattr(task_app, "DATABASE", str(database))

    task_app.init_db()

    with task_app.get_db() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
        task = conn.execute("SELECT * FROM tasks WHERE id = 1").fetchone()
    assert "owner_id" in columns
    assert task["title"] == "Legacy"
