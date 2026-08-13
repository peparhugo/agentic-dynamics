from xml.etree import ElementTree as ET

import pytest

from app import SOAP_NS, TASK_NS, create_app


@pytest.fixture
def client(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "tasks.db")})
    return app.test_client()


def call(client, operation, **fields):
    envelope = ET.Element(f"{{{SOAP_NS}}}Envelope")
    body = ET.SubElement(envelope, f"{{{SOAP_NS}}}Body")
    request = ET.SubElement(body, f"{{{TASK_NS}}}{operation}")
    for name, value in fields.items():
        ET.SubElement(request, f"{{{TASK_NS}}}{name}").text = str(value)
    return client.post("/soap", data=ET.tostring(envelope), content_type="text/xml")


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


def test_create_task_defaults_to_pending(client):
    response = call(client, "CreateTask", title="Write tests")

    assert response.status_code == 201
    assert tasks(response)[0]["title"] == "Write tests"
    assert tasks(response)[0]["status"] == "pending"
    assert tasks(response)[0]["created_at"]


def test_create_requires_title(client):
    response = call(client, "CreateTask")

    assert response.status_code == 400
    assert fault(response) == "title is required"


def test_list_tasks_newest_first(client):
    call(client, "CreateTask", title="First")
    call(client, "CreateTask", title="Second")

    response = call(client, "ListTasks")

    assert response.status_code == 200
    assert [task["title"] for task in tasks(response)] == ["Second", "First"]


def test_get_task_and_not_found(client):
    created = call(client, "CreateTask", title="Existing")
    task_id = tasks(created)[0]["id"]

    assert tasks(call(client, "GetTask", id=task_id))[0]["title"] == "Existing"
    missing = call(client, "GetTask", id=999)
    assert missing.status_code == 404
    assert fault(missing) == "task not found"


def test_update_title_and_status(client):
    created = call(client, "CreateTask", title="Old")
    task_id = tasks(created)[0]["id"]

    response = call(
        client, "UpdateTask", id=task_id, title="New", status="completed"
    )

    assert response.status_code == 200
    assert tasks(response)[0]["title"] == "New"
    assert tasks(response)[0]["status"] == "completed"


def test_update_missing_task_returns_not_found(client):
    response = call(client, "UpdateTask", id=999, status="completed")

    assert response.status_code == 404
    assert fault(response) == "task not found"


def test_invalid_xml_returns_soap_fault(client):
    response = client.post("/soap", data="not XML", content_type="text/xml")

    assert response.status_code == 400
    assert fault(response) == "invalid SOAP XML"
