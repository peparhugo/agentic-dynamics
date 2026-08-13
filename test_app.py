import xml.etree.ElementTree as ET

import app as task_app
import pytest


SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
TASK = "urn:tasks"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "tasks.db"))
    task_app.init_db()
    return task_app.app.test_client()


def soap_request(operation, fields=""):
    return (
        f'<soap:Envelope xmlns:soap="{SOAP}" xmlns:t="{TASK}">'
        f"<soap:Body><t:{operation}>{fields}</t:{operation}></soap:Body>"
        "</soap:Envelope>"
    )


def xml(response):
    return ET.fromstring(response.data)


def task_values(response):
    task = xml(response).find(f".//{{{TASK}}}CreateTaskResponse/Task")
    if task is None:
        task = xml(response).find(f".//{{{TASK}}}GetTaskResponse/Task")
    if task is None:
        task = xml(response).find(f".//{{{TASK}}}UpdateTaskResponse/Task")
    return {child.tag: child.text for child in task}


def fault_text(response):
    return xml(response).findtext(f".//{{{SOAP}}}Fault/faultstring")


def test_create_task_uses_pending_status(client):
    response = client.post("/soap", data=soap_request("CreateTask", "<title>Write tests</title>"))

    assert response.status_code == 201
    assert response.content_type.startswith("text/xml")
    assert task_values(response)["title"] == "Write tests"
    assert task_values(response)["status"] == "pending"
    assert task_values(response)["created_at"]


def test_create_task_requires_title(client):
    response = client.post("/soap", data=soap_request("CreateTask"))

    assert response.status_code == 400
    assert fault_text(response) == "title is required"


def test_list_tasks_is_newest_first(client):
    client.post("/soap", data=soap_request("CreateTask", "<title>Older</title>"))
    client.post("/soap", data=soap_request("CreateTask", "<title>Newer</title>"))

    response = client.post("/soap", data=soap_request("ListTasks"))
    tasks = xml(response).findall(f".//{{{TASK}}}ListTasksResponse/Task")

    assert response.status_code == 200
    assert [task.findtext("title") for task in tasks] == ["Newer", "Older"]


def test_get_task_and_missing_task(client):
    created = client.post("/soap", data=soap_request("CreateTask", "<title>Read</title>"))
    identifier = task_values(created)["id"]

    response = client.post("/soap", data=soap_request("GetTask", f"<id>{identifier}</id>"))
    missing = client.post("/soap", data=soap_request("GetTask", "<id>999</id>"))

    assert task_values(response)["title"] == "Read"
    assert missing.status_code == 404
    assert fault_text(missing) == "task not found"


def test_update_task_allows_partial_updates(client):
    created = client.post("/soap", data=soap_request("CreateTask", "<title>Draft</title>"))
    identifier = task_values(created)["id"]

    response = client.post(
        "/soap", data=soap_request("UpdateTask", f"<id>{identifier}</id><status>complete</status>")
    )

    assert task_values(response)["title"] == "Draft"
    assert task_values(response)["status"] == "complete"


def test_rejects_invalid_soap_requests(client):
    malformed = client.post("/soap", data="not xml")
    unknown = client.post("/soap", data=soap_request("DeleteTask"))

    assert malformed.status_code == 400
    assert fault_text(malformed) == "invalid SOAP XML"
    assert unknown.status_code == 400
    assert fault_text(unknown) == "unknown SOAP operation"
