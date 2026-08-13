from xml.etree import ElementTree as ET
import sqlite3

import pytest

from app import SOAP_NS, TASK_NS, create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "tasks.db"),
            "JWT_SECRET_KEY": "test-secret",
        }
    )
    return app.test_client()


def register_and_login(client, username="alice", password="secret"):
    registered = client.post(
        "/auth/register", json={"username": username, "password": password}
    )
    assert registered.status_code == 201
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    return response.json["token"]


@pytest.fixture
def token(client):
    return register_and_login(client)


def call(client, operation, token=None, **fields):
    envelope = ET.Element(f"{{{SOAP_NS}}}Envelope")
    body = ET.SubElement(envelope, f"{{{SOAP_NS}}}Body")
    request = ET.SubElement(body, f"{{{TASK_NS}}}{operation}")
    for name, value in fields.items():
        ET.SubElement(request, f"{{{TASK_NS}}}{name}").text = str(value)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post(
        "/soap",
        data=ET.tostring(envelope),
        content_type="text/xml",
        headers=headers,
    )


def tasks(response):
    root = ET.fromstring(response.data)
    output = []
    for element in root.findall(f".//{{{TASK_NS}}}task"):
        output.append(
            {
                child.tag.rsplit("}", 1)[-1]: child.text
                for child in element
            }
        )
    return output


def fault(response):
    root = ET.fromstring(response.data)
    return root.findtext(f".//{{{SOAP_NS}}}Fault/faultstring")


def test_create_task_defaults_to_pending(client, token):
    response = call(client, "CreateTask", token, title="Write tests")

    assert response.status_code == 201
    assert tasks(response)[0]["title"] == "Write tests"
    assert tasks(response)[0]["status"] == "pending"
    assert tasks(response)[0]["created_at"]


def test_create_requires_title(client, token):
    response = call(client, "CreateTask", token)

    assert response.status_code == 400
    assert fault(response) == "title is required"


def test_list_tasks_newest_first(client, token):
    call(client, "CreateTask", token, title="First")
    call(client, "CreateTask", token, title="Second")

    response = call(client, "ListTasks", token)

    assert response.status_code == 200
    assert [task["title"] for task in tasks(response)] == ["Second", "First"]


def test_get_task_and_not_found(client, token):
    created = call(client, "CreateTask", token, title="Existing")
    task_id = tasks(created)[0]["id"]

    assert tasks(call(client, "GetTask", token, id=task_id))[0]["title"] == "Existing"
    missing = call(client, "GetTask", token, id=999)
    assert missing.status_code == 404
    assert fault(missing) == "task not found"


def test_update_title_and_status(client, token):
    created = call(client, "CreateTask", token, title="Old")
    task_id = tasks(created)[0]["id"]

    response = call(
        client, "UpdateTask", token, id=task_id, title="New", status="completed"
    )

    assert response.status_code == 200
    assert tasks(response)[0]["title"] == "New"
    assert tasks(response)[0]["status"] == "completed"


def test_update_missing_task_returns_not_found(client, token):
    response = call(client, "UpdateTask", token, id=999, status="completed")

    assert response.status_code == 404
    assert fault(response) == "task not found"


def test_invalid_xml_returns_soap_fault(client, token):
    response = client.post(
        "/soap",
        data="not XML",
        content_type="text/xml",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert fault(response) == "invalid SOAP XML"


def test_register_hashes_password_and_rejects_duplicate(client):
    response = client.post(
        "/auth/register", json={"username": "alice", "password": "secret"}
    )

    assert response.status_code == 201
    assert response.json["username"] == "alice"
    duplicate = client.post(
        "/auth/register", json={"username": "alice", "password": "other"}
    )
    assert duplicate.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"username": "", "password": "secret"},
        {"username": "alice", "password": ""},
    ],
)
def test_register_validates_credentials(client, payload):
    assert client.post("/auth/register", json=payload).status_code == 400


def test_login_rejects_bad_credentials(client):
    client.post("/auth/register", json={"username": "alice", "password": "secret"})

    response = client.post(
        "/auth/login", json={"username": "alice", "password": "wrong"}
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer invalid"}, {"Authorization": "Basic abc"}],
)
def test_tasks_require_valid_jwt(client, headers):
    response = client.post("/soap", data="irrelevant", headers=headers)

    assert response.status_code == 401


def test_users_only_see_and_update_their_own_tasks(client):
    alice_token = register_and_login(client, "alice")
    bob_token = register_and_login(client, "bob")
    created = call(client, "CreateTask", alice_token, title="Alice task")
    task_id = tasks(created)[0]["id"]

    assert tasks(call(client, "ListTasks", bob_token)) == []
    assert call(client, "GetTask", bob_token, id=task_id).status_code == 404
    assert (
        call(client, "UpdateTask", bob_token, id=task_id, status="completed").status_code
        == 404
    )
    assert tasks(call(client, "GetTask", alice_token, id=task_id))[0]["status"] == "pending"


def test_existing_tasks_are_preserved_during_migration(tmp_path):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
            ("Legacy task", "pending", "2026-01-01T00:00:00+00:00"),
        )

    create_app({"TESTING": True, "DATABASE": str(database)})

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT title, owner_id FROM tasks WHERE id = 1"
        ).fetchone()
        assert row[0] == "Legacy task"
        assert row[1] is not None
