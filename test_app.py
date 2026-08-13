from xml.etree import ElementTree as ET

import pytest

import app as task_app


SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
TASK_NS = "urn:task-service"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(task_app, "DATABASE", str(tmp_path / "test.db"))
    task_app.init_db()
    task_app.app.config.update(TESTING=True)
    return task_app.app.test_client()


def call(client, operation, **values):
    fields = "".join(f"<tns:{key}>{value}</tns:{key}>" for key, value in values.items())
    xml = f"""<soap:Envelope xmlns:soap="{SOAP_ENV}" xmlns:tns="{TASK_NS}">
      <soap:Body><tns:{operation}>{fields}</tns:{operation}></soap:Body>
    </soap:Envelope>"""
    return client.post("/soap", data=xml, content_type="text/xml")


def task_values(response):
    root = ET.fromstring(response.data)
    task = root.find(f".//{{{TASK_NS}}}task")
    assert task is not None
    return {child.tag.rsplit("}", 1)[-1]: child.text for child in task}


def test_create_get_and_update_task(client):
    created = call(client, "CreateTask", title="Write tests")
    assert created.status_code == 201
    assert task_values(created)["status"] == "pending"

    fetched = call(client, "GetTask", id=1)
    assert task_values(fetched)["title"] == "Write tests"

    updated = call(client, "UpdateTask", id=1, title="Ship API", status="done")
    values = task_values(updated)
    assert values["id"] == "1"
    assert values["title"] == "Ship API"
    assert values["status"] == "done"


def test_list_tasks_newest_first(client):
    call(client, "CreateTask", title="First")
    call(client, "CreateTask", title="Second")
    response = call(client, "ListTasks")
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
def test_soap_faults(client, operation, values, status, message):
    response = call(client, operation, **values)
    assert response.status_code == status
    assert response.content_type.startswith("text/xml")
    assert message in response.get_data(as_text=True)


def test_wsdl_is_available(client):
    response = client.get("/soap?wsdl")
    assert response.status_code == 200
    assert b"TaskService" in response.data
