from xml.etree import ElementTree as ET

import pytest

import app as task_app


SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
TASK_NS = "urn:task-service"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "test.db"))
    task_app.init_db()
    task_app.app.config.update(TESTING=True, JWT_SECRET_KEY="test-secret")
    return task_app.app.test_client()


@pytest.fixture()
def auth(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})
    token = client.post(
        "/auth/login", json={"username": "alice", "password": "secret"}
    ).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def call(client, operation, headers=None, **values):
    fields = "".join(f"<tns:{key}>{value}</tns:{key}>" for key, value in values.items())
    xml = f"""<soap:Envelope xmlns:soap="{SOAP_ENV}" xmlns:tns="{TASK_NS}">
      <soap:Body><tns:{operation}>{fields}</tns:{operation}></soap:Body>
    </soap:Envelope>"""
    return client.post("/soap", data=xml, content_type="text/xml", headers=headers)


def task_values(response):
    root = ET.fromstring(response.data)
    task = root.find(f".//{{{TASK_NS}}}task")
    assert task is not None
    return {child.tag.rsplit("}", 1)[-1]: child.text for child in task}


def test_create_get_and_update_task(client, auth):
    created = call(client, "CreateTask", headers=auth, title="Write tests")
    assert created.status_code == 201
    assert task_values(created)["status"] == "pending"

    fetched = call(client, "GetTask", headers=auth, id=1)
    assert task_values(fetched)["title"] == "Write tests"

    updated = call(
        client, "UpdateTask", headers=auth, id=1, title="Ship API", status="done"
    )
    values = task_values(updated)
    assert values["id"] == "1"
    assert values["title"] == "Ship API"
    assert values["status"] == "done"


def test_list_tasks_newest_first(client, auth):
    call(client, "CreateTask", headers=auth, title="First")
    call(client, "CreateTask", headers=auth, title="Second")
    response = call(client, "ListTasks", headers=auth)
    root = ET.fromstring(response.data)
    titles = [node.text for node in root.findall(f".//{{{TASK_NS}}}title")]
    assert titles == ["Second", "First"]


@pytest.mark.parametrize(
    ("operation", "values", "status", "message"),
    [
        ("CreateTask", {}, 400, "title is required"),
        ("GetTask", {"id": 999}, 404, "task not found"),
        ("UpdateTask", {"id": 999, "status": "done"}, 404, "task not found"),
    ],
)
def test_soap_faults(client, auth, operation, values, status, message):
    response = call(client, operation, headers=auth, **values)
    assert response.status_code == status
    assert response.content_type.startswith("text/xml")
    assert message in response.get_data(as_text=True)


def test_wsdl_is_available(client):
    response = client.get("/soap?wsdl")
    assert response.status_code == 200
    assert b"TaskService" in response.data


def test_register_login_and_password_hash(client):
    response = client.post(
        "/auth/register", json={"username": "bob", "password": "plain-text"}
    )
    assert response.status_code == 201
    assert response.get_json()["username"] == "bob"

    with task_app.get_db() as connection:
        password_hash = connection.execute(
            "SELECT password_hash FROM users WHERE username = 'bob'"
        ).fetchone()["password_hash"]
    assert password_hash != "plain-text"

    login = client.post(
        "/auth/login", json={"username": "bob", "password": "plain-text"}
    )
    assert login.status_code == 200
    assert login.get_json()["token"].count(".") == 2


def test_duplicate_registration_and_bad_login(client):
    credentials = {"username": "bob", "password": "secret"}
    assert client.post("/auth/register", json=credentials).status_code == 201
    assert client.post("/auth/register", json=credentials).status_code == 409
    assert client.post(
        "/auth/login", json={"username": "bob", "password": "wrong"}
    ).status_code == 401


@pytest.mark.parametrize(
    ("path", "method"),
    [("/tasks", "get"), ("/tasks", "post"), ("/tasks/1", "get")],
)
def test_tasks_require_valid_token(client, path, method):
    response = getattr(client, method)(path, json={} if method == "post" else None)
    assert response.status_code == 401
    invalid = getattr(client, method)(
        path,
        json={} if method == "post" else None,
        headers={"Authorization": "Bearer invalid"},
    )
    assert invalid.status_code == 401


def test_soap_requires_token(client):
    response = call(client, "ListTasks")
    assert response.status_code == 401
    assert response.content_type.startswith("text/xml")


def test_users_only_access_their_own_tasks(client, auth):
    first = client.post("/tasks", json={"title": "Alice task"}, headers=auth)
    assert first.status_code == 201
    task_id = first.get_json()["id"]

    client.post("/auth/register", json={"username": "bob", "password": "secret"})
    token = client.post(
        "/auth/login", json={"username": "bob", "password": "secret"}
    ).get_json()["token"]
    bob_auth = {"Authorization": f"Bearer {token}"}

    assert client.get("/tasks", headers=bob_auth).get_json() == []
    assert client.get(f"/tasks/{task_id}", headers=bob_auth).status_code == 404
    assert client.patch(
        f"/tasks/{task_id}", json={"status": "done"}, headers=bob_auth
    ).status_code == 404
    assert client.get(f"/tasks/{task_id}", headers=auth).get_json()["status"] == "pending"


def test_put_completed_enqueues_owner_notification(client, auth, monkeypatch):
    created = client.post("/tasks", json={"title": "Ship API"}, headers=auth)
    task_id = created.get_json()["id"]
    calls = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda user_email, task_title: calls.append((user_email, task_title)),
    )

    response = client.put(
        f"/tasks/{task_id}", json={"status": "completed"}, headers=auth
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "completed"
    assert calls == [("alice", "Ship API")]


def test_notification_only_on_put_transition_to_completed(client, auth, monkeypatch):
    created = client.post("/tasks", json={"title": "Write tests"}, headers=auth)
    task_id = created.get_json()["id"]
    calls = []
    monkeypatch.setattr(
        task_app.send_notification_email,
        "delay",
        lambda *args: calls.append(args),
    )

    client.put(f"/tasks/{task_id}", json={"status": "pending"}, headers=auth)
    client.patch(f"/tasks/{task_id}", json={"status": "completed"}, headers=auth)
    client.put(f"/tasks/{task_id}", json={"status": "completed"}, headers=auth)

    assert calls == []


def test_migration_preserves_existing_tasks(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    import sqlite3

    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, "
            "status TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO tasks VALUES (1, 'Legacy', 'pending', '2024-01-01')"
        )
    monkeypatch.setattr(task_app, "DATABASE", str(database))
    task_app.init_db()
    with task_app.get_db() as connection:
        row = connection.execute("SELECT * FROM tasks WHERE id = 1").fetchone()
    assert row["title"] == "Legacy"
    assert row["owner_id"] is None
