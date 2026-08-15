import time
import xml.etree.ElementTree as ET

import pytest

import app as app_module
from app import app

SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
SERVICE_NS = "urn:tasks"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DATABASE", str(tmp_path / "test.db"))
    app_module.init_db()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def local(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def soap(client, operation, **params):
    inner = "".join(f"<{k}>{v}</{k}>" for k, v in params.items())
    body = f'<{operation} xmlns="{SERVICE_NS}">{inner}</{operation}>'
    envelope = (
        '<?xml version="1.0"?>'
        f'<soap:Envelope xmlns:soap="{SOAP_NS}"><soap:Body>{body}</soap:Body></soap:Envelope>'
    )
    return client.post("/tasks", data=envelope, content_type="text/xml")


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


# ── Create ─────────────────────────────────────────────────────

def test_create_task(client):
    resp = soap(client, "CreateTask", title="Buy milk")
    assert resp.status_code == 200
    task = response_task(resp)
    assert task["title"] == "Buy milk"
    assert task["status"] == "pending"
    assert task["id"] == "1"
    assert task["created_at"]


def test_create_missing_title_returns_400(client):
    resp = soap(client, "CreateTask", title="")
    assert resp.status_code == 400
    assert "title" in fault_string(resp)


# ── List ───────────────────────────────────────────────────────

def test_list_empty(client):
    resp = soap(client, "ListTasks")
    assert resp.status_code == 200
    body = parse_body(resp)
    root_elem = list(body)[0]
    assert local(root_elem.tag) == "ListTasksResponse"
    assert list(root_elem) == []


def test_list_ordered_desc(client):
    soap(client, "CreateTask", title="first")
    time.sleep(0.01)
    soap(client, "CreateTask", title="second")
    resp = soap(client, "ListTasks")
    body = parse_body(resp)
    root_elem = list(body)[0]
    tasks = [task_dict(c) for c in root_elem]
    assert [t["title"] for t in tasks] == ["second", "first"]


# ── Get ────────────────────────────────────────────────────────

def test_get_task(client):
    soap(client, "CreateTask", title="hello")
    resp = soap(client, "GetTask", id="1")
    assert resp.status_code == 200
    task = response_task(resp)
    assert task["id"] == "1"
    assert task["title"] == "hello"


def test_get_task_not_found_returns_404(client):
    resp = soap(client, "GetTask", id="999")
    assert resp.status_code == 404
    assert "not found" in fault_string(resp)


# ── Update ─────────────────────────────────────────────────────

def test_update_title(client):
    soap(client, "CreateTask", title="old")
    resp = soap(client, "UpdateTask", id="1", title="new")
    assert resp.status_code == 200
    task = response_task(resp)
    assert task["title"] == "new"
    assert task["status"] == "pending"


def test_update_status(client):
    soap(client, "CreateTask", title="old")
    resp = soap(client, "UpdateTask", id="1", status="done")
    task = response_task(resp)
    assert task["status"] == "done"
    assert task["title"] == "old"


def test_update_both(client):
    soap(client, "CreateTask", title="old")
    resp = soap(client, "UpdateTask", id="1", title="new", status="done")
    task = response_task(resp)
    assert task["title"] == "new"
    assert task["status"] == "done"


def test_update_not_found_returns_404(client):
    resp = soap(client, "UpdateTask", id="5", title="x")
    assert resp.status_code == 404


# ── SOAP protocol robustness ───────────────────────────────────

def test_invalid_xml_returns_400(client):
    resp = client.post("/tasks", data="not xml", content_type="text/xml")
    assert resp.status_code == 400


def test_empty_body_returns_400(client):
    resp = client.post("/tasks", data="", content_type="text/xml")
    assert resp.status_code == 400


def test_unknown_operation_returns_400(client):
    resp = soap(client, "DeleteTask", id="1")
    assert resp.status_code == 400
    assert "unknown operation" in fault_string(resp)
