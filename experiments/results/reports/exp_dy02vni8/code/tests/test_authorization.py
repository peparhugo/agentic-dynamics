from conftest import auth_headers, create_task


def test_only_creator_can_delete(client, users):
    created = create_task(client, users["alice"]["token"], title="Alice's task")
    task_id = created.get_json()["id"]

    resp = client.delete(f"/tasks/{task_id}", headers=auth_headers(users["bob"]["token"]))
    assert resp.status_code == 403

    resp = client.delete(f"/tasks/{task_id}", headers=auth_headers(users["alice"]["token"]))
    assert resp.status_code == 200


def test_assignee_can_update_status(client, users):
    created = create_task(client, users["alice"]["token"], title="Shared task")
    task_id = created.get_json()["id"]
    client.post(
        f"/tasks/{task_id}/assign",
        json={"username": "bob"},
        headers=auth_headers(users["alice"]["token"]),
    )

    resp = client.put(
        f"/tasks/{task_id}",
        json={"status": "in_progress"},
        headers=auth_headers(users["bob"]["token"]),
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "in_progress"


def test_unrelated_user_cannot_update(client, users):
    created = create_task(client, users["alice"]["token"], title="Private")
    task_id = created.get_json()["id"]

    resp = client.put(
        f"/tasks/{task_id}", json={"title": "hacked"}, headers=auth_headers(users["carol"]["token"])
    )
    assert resp.status_code == 403


def test_assignee_cannot_reassign(client, users):
    created = create_task(client, users["alice"]["token"], title="Assignment control")
    task_id = created.get_json()["id"]
    client.post(
        f"/tasks/{task_id}/assign",
        json={"username": "bob"},
        headers=auth_headers(users["alice"]["token"]),
    )

    resp = client.post(
        f"/tasks/{task_id}/assign",
        json={"username": "carol"},
        headers=auth_headers(users["bob"]["token"]),
    )
    assert resp.status_code == 403


def test_unrelated_user_cannot_assign(client, users):
    created = create_task(client, users["alice"]["token"], title="No touch")
    task_id = created.get_json()["id"]

    resp = client.post(
        f"/tasks/{task_id}/assign",
        json={"username": "bob"},
        headers=auth_headers(users["bob"]["token"]),
    )
    assert resp.status_code == 403


def test_any_authenticated_user_can_read(client, users):
    created = create_task(client, users["alice"]["token"], title="Readable")
    task_id = created.get_json()["id"]
    resp = client.get(f"/tasks/{task_id}", headers=auth_headers(users["carol"]["token"]))
    assert resp.status_code == 200


def test_any_authenticated_user_can_list(client, users):
    create_task(client, users["alice"]["token"], title="Visible")
    resp = client.get("/tasks", headers=auth_headers(users["carol"]["token"]))
    assert resp.status_code == 200
    assert len(resp.get_json()["items"]) == 1
