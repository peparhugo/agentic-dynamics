import time
import xml.etree.ElementTree as ET
from unittest import mock

import pytest

import app as app_module
from app import app

SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
SERVICE_NS = "urn:tasks"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DATABASE", str(tmp_path / "test.db"))
    monkeypatch.setattr(app_module, "SECRET_KEY", "test-secret-key-that-is-long-enough-123")
    app_module.init_db()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def register(client, username="alice", password="secret123"):
    return client.post(
        "/auth/register", json={"username": username, "password": password}
    )


def login(client, username="alice", password="secret123"):
    return client.post(
        "/auth/login", json={"username": username, "password": password}
    )


@pytest.fixture()
def auth(client):
    register(client)
    return {"Authorization": f"Bearer {login(client).get_json()['token']}"}


def local(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def soap(client, operation, headers=None, **params):
    inner = "".join(f"<{k}>{v}</{k}>" for k, v in params.items())
    body = f'<{operation} xmlns="{SERVICE_NS}">{inner}</{operation}>'
    envelope = (
        '<?xml version="1.0"?>'
        f'<soap:Envelope xmlns:soap="{SOAP_NS}"><soap:Body>{body}</soap:Body></soap:Envelope>'
    )
    return client.post(
        "/tasks", data=envelope, content_type="text/xml", headers=headers
    )


def parse_body(resp):
    root = ET.fromstring(resp.data)
    return root.find(f"{{{SOAP_NS}}}Body")


def task_dict(elem):
    return {local(c.tag): (c.text or "").strip() for c in elem}


def response_task(resp):
    body = parse_body(resp)
    elem = list(body)[0]
    assert local(elem.tag).endswith("Response")
    return task_dict(elem)


def fault_string(resp):
    body = parse_body(resp)
    fault = list(body)[0]
    assert local(fault.tag) == "Fault"
    for c in fault:
        if local(c.tag) == "faultstring":
            return (c.text or "").strip()
    return ""


# ── Auth: register / login ─────────────────────────────────────

def test_register_creates_user(client):
    resp = register(client)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["id"] == 1
    assert data["username"] == "alice"


def test_register_duplicate_username_returns_409(client):
    register(client)
    resp = register(client)
    assert resp.status_code == 409


def test_register_requires_fields(client):
    assert client.post("/auth/register", json={"username": "bob"}).status_code == 400
    assert client.post("/auth/register", json={"password": "x"}).status_code == 400


def test_login_returns_token(client):
    register(client)
    resp = login(client)
    assert resp.status_code == 200
    token = resp.get_json()["token"]
    assert isinstance(token, str) and token


def test_login_wrong_password_returns_401(client):
    register(client)
    assert login(client, password="wrong").status_code == 401


def test_login_unknown_user_returns_401(client):
    assert login(client, username="nobody").status_code == 401


# ── Auth: protection ───────────────────────────────────────────

def test_tasks_requires_token(client):
    resp = soap(client, "ListTasks")
    assert resp.status_code == 401
    assert "token" in fault_string(resp)


def test_tasks_rejects_invalid_token(client):
    resp = soap(client, "ListTasks", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


# ── Create ─────────────────────────────────────────────────────

def test_create_task(client, auth):
    resp = soap(client, "CreateTask", headers=auth, title="Buy milk")
    assert resp.status_code == 200
    task = response_task(resp)
    assert task["title"] == "Buy milk"
    assert task["status"] == "pending"
    assert task["id"] == "1"
    assert task["created_at"]


def test_create_missing_title_returns_400(client, auth):
    resp = soap(client, "CreateTask", headers=auth, title="")
    assert resp.status_code == 400
    assert "title" in fault_string(resp)


# ── List ───────────────────────────────────────────────────────

def test_list_empty(client, auth):
    resp = soap(client, "ListTasks", headers=auth)
    assert resp.status_code == 200
    body = parse_body(resp)
    root_elem = list(body)[0]
    assert local(root_elem.tag) == "ListTasksResponse"
    assert list(root_elem) == []


def test_list_ordered_desc(client, auth):
    soap(client, "CreateTask", headers=auth, title="first")
    time.sleep(0.01)
    soap(client, "CreateTask", headers=auth, title="second")
    resp = soap(client, "ListTasks", headers=auth)
    body = parse_body(resp)
    root_elem = list(body)[0]
    tasks = [task_dict(c) for c in root_elem]
    assert [t["title"] for t in tasks] == ["second", "first"]


# ── Get ────────────────────────────────────────────────────────

def test_get_task(client, auth):
    soap(client, "CreateTask", headers=auth, title="hello")
    resp = soap(client, "GetTask", headers=auth, id="1")
    assert resp.status_code == 200
    task = response_task(resp)
    assert task["id"] == "1"
    assert task["title"] == "hello"


def test_get_task_not_found_returns_404(client, auth):
    resp = soap(client, "GetTask", headers=auth, id="999")
    assert resp.status_code == 404
    assert "not found" in fault_string(resp)


# ── Update ─────────────────────────────────────────────────────

def test_update_title(client, auth):
    soap(client, "CreateTask", headers=auth, title="old")
    resp = soap(client, "UpdateTask", headers=auth, id="1", title="new")
    assert resp.status_code == 200
    task = response_task(resp)
    assert task["title"] == "new"
    assert task["status"] == "pending"


def test_update_status(client, auth):
    soap(client, "CreateTask", headers=auth, title="old")
    resp = soap(client, "UpdateTask", headers=auth, id="1", status="done")
    task = response_task(resp)
    assert task["status"] == "done"
    assert task["title"] == "old"


def test_update_both(client, auth):
    soap(client, "CreateTask", headers=auth, title="old")
    resp = soap(client, "UpdateTask", headers=auth, id="1", title="new", status="done")
    task = response_task(resp)
    assert task["title"] == "new"
    assert task["status"] == "done"


def test_update_not_found_returns_404(client, auth):
    resp = soap(client, "UpdateTask", headers=auth, id="5", title="x")
    assert resp.status_code == 404


# ── Ownership isolation ────────────────────────────────────────

def test_user_does_not_see_other_users_tasks(client):
    register(client, "alice")
    alice = {"Authorization": f"Bearer {login(client, 'alice').get_json()['token']}"}
    soap(client, "CreateTask", headers=alice, title="alice task")

    register(client, "bob", "bobpass")
    bob = {"Authorization": f"Bearer {login(client, 'bob', 'bobpass').get_json()['token']}"}

    resp = soap(client, "ListTasks", headers=bob)
    body = parse_body(resp)
    root_elem = list(body)[0]
    assert list(root_elem) == []

    resp = soap(client, "GetTask", headers=bob, id="1")
    assert resp.status_code == 404


# ── SOAP protocol robustness ───────────────────────────────────

def test_invalid_xml_returns_400(client, auth):
    resp = client.post(
        "/tasks", data="not xml", content_type="text/xml", headers=auth
    )
    assert resp.status_code == 400


def test_empty_body_returns_400(client, auth):
    resp = client.post("/tasks", data="", content_type="text/xml", headers=auth)
    assert resp.status_code == 400


def test_unknown_operation_returns_400(client, auth):
    resp = soap(client, "DeleteTask", headers=auth, id="1")
    assert resp.status_code == 400
    assert "unknown operation" in fault_string(resp)


# ── Notification trigger ────────────────────────────────────────

@pytest.fixture()
def email_task(monkeypatch):
    fake = mock.MagicMock(name="send_notification_email")
    monkeypatch.setattr(app_module, "send_notification_email", fake)
    return fake


def test_update_to_completed_triggers_notification(client, auth, email_task):
    soap(client, "CreateTask", headers=auth, title="Buy milk")
    resp = soap(client, "UpdateTask", headers=auth, id="1", status="completed")
    assert resp.status_code == 200
    assert response_task(resp)["status"] == "completed"
    email_task.delay.assert_called_once_with("alice@example.com", "Buy milk")


def test_update_to_completed_uses_custom_email(client, monkeypatch):
    email_task = mock.MagicMock(name="send_notification_email")
    monkeypatch.setattr(app_module, "send_notification_email", email_task)
    client.post(
        "/auth/register",
        json={"username": "dave", "password": "x", "email": "dave@corp.com"},
    )
    dave = {"Authorization": f"Bearer {login(client, 'dave', 'x').get_json()['token']}"}
    soap(client, "CreateTask", headers=dave, title="Ship it")
    soap(client, "UpdateTask", headers=dave, id="1", status="completed")
    email_task.delay.assert_called_once_with("dave@corp.com", "Ship it")


def test_update_to_other_status_does_not_trigger(client, auth, email_task):
    soap(client, "CreateTask", headers=auth, title="Buy milk")
    resp = soap(client, "UpdateTask", headers=auth, id="1", status="done")
    assert resp.status_code == 200
    email_task.delay.assert_not_called()


def test_update_title_only_does_not_trigger(client, auth, email_task):
    soap(client, "CreateTask", headers=auth, title="Buy milk")
    resp = soap(client, "UpdateTask", headers=auth, id="1", title="new")
    assert resp.status_code == 200
    email_task.delay.assert_not_called()


def test_completing_an_already_completed_task_does_not_trigger_again(client, auth, email_task):
    soap(client, "CreateTask", headers=auth, title="Buy milk")
    soap(client, "UpdateTask", headers=auth, id="1", status="completed")
    email_task.delay.assert_called_once()
    email_task.reset_mock()
    resp = soap(client, "UpdateTask", headers=auth, id="1", status="completed")
    assert resp.status_code == 200
    email_task.delay.assert_not_called()


def test_notification_task_emails_owner(capsys):
    result = app_module.send_notification_email("alice@example.com", "Buy milk")
    assert result == {"to": "alice@example.com", "title": "Buy milk"}
    assert "alice@example.com" in capsys.readouterr().out
