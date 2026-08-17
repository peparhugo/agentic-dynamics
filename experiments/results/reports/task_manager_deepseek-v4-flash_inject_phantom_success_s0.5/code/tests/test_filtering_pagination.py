import pytest

from conftest import auth_headers, create_task


@pytest.fixture()
def task_fixture(client, users, priority_ids, category_ids):
    def make(title, **kwargs):
        defaults = {"creator": "alice"}
        defaults.update(kwargs)
        creator = defaults.pop("creator")
        return create_task(client, users[creator]["token"], title=title, **defaults)

    return make


def test_list_tasks_all(client, users):
    create_task(client, users["alice"]["token"], title="A")
    create_task(client, users["bob"]["token"], title="B")
    resp = client.get("/tasks", headers=auth_headers(users["alice"]["token"]))
    assert resp.status_code == 200
    assert len(resp.get_json()["items"]) == 2


def test_pagination_defaults(client, users):
    for i in range(25):
        create_task(client, users["alice"]["token"], title=f"Task {i}")
    resp = client.get("/tasks", headers=auth_headers(users["alice"]["token"]))
    data = resp.get_json()
    assert len(data["items"]) == 20
    assert data["pagination"]["total"] == 25
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["per_page"] == 20
    assert data["pagination"]["pages"] == 2


def test_pagination_second_page(client, users):
    for i in range(25):
        create_task(client, users["alice"]["token"], title=f"Task {i:02d}")
    resp = client.get(
        "/tasks?page=2&per_page=10", headers=auth_headers(users["alice"]["token"])
    )
    data = resp.get_json()
    assert len(data["items"]) == 10
    assert data["pagination"]["page"] == 2
    titles = [t["title"] for t in data["items"]]
    assert titles == [f"Task {i:02d}" for i in range(10, 20)]


def test_pagination_page_out_of_range(client, users):
    for i in range(5):
        create_task(client, users["alice"]["token"], title=f"Task {i}")
    resp = client.get(
        "/tasks?page=10&per_page=5", headers=auth_headers(users["alice"]["token"])
    )
    data = resp.get_json()
    assert data["items"] == []
    assert data["pagination"]["pages"] == 1


def test_pagination_per_page_cap(client, users):
    for i in range(150):
        create_task(client, users["alice"]["token"], title=f"Task {i}")
    resp = client.get(
        "/tasks?per_page=1000", headers=auth_headers(users["alice"]["token"])
    )
    assert resp.get_json()["pagination"]["per_page"] == 100


def test_pagination_invalid_page(client, users):
    create_task(client, users["alice"]["token"], title="A")
    resp = client.get(
        "/tasks?page=abc", headers=auth_headers(users["alice"]["token"])
    )
    assert resp.status_code == 400


def test_filter_by_status(client, users):
    create_task(client, users["alice"]["token"], title="Pending task")
    create_task(client, users["alice"]["token"], title="Done task", status="completed")
    resp = client.get(
        "/tasks?status=completed", headers=auth_headers(users["alice"]["token"])
    )
    items = resp.get_json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Done task"


def test_filter_by_invalid_status(client, users):
    create_task(client, users["alice"]["token"], title="A")
    resp = client.get(
        "/tasks?status=bogus", headers=auth_headers(users["alice"]["token"])
    )
    assert resp.status_code == 400


def test_filter_by_priority(client, users, priority_ids):
    create_task(client, users["alice"]["token"], title="Urgent one", priority_id=priority_ids["urgent"])
    create_task(client, users["alice"]["token"], title="Low one", priority_id=priority_ids["low"])
    resp = client.get(
        "/tasks?priority=urgent", headers=auth_headers(users["alice"]["token"])
    )
    items = resp.get_json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Urgent one"


def test_filter_by_category(client, users, category_ids):
    create_task(client, users["alice"]["token"], title="Work one", category_id=category_ids["Work"])
    create_task(client, users["alice"]["token"], title="Personal one", category_id=category_ids["Personal"])
    resp = client.get(
        "/tasks?category=Work", headers=auth_headers(users["alice"]["token"])
    )
    items = resp.get_json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Work one"


def test_filter_by_assignee(client, users):
    created = create_task(client, users["alice"]["token"], title="Mine")
    task_id = created.get_json()["id"]
    client.post(
        f"/tasks/{task_id}/assign",
        json={"username": "bob"},
        headers=auth_headers(users["alice"]["token"]),
    )
    create_task(client, users["alice"]["token"], title="Unassigned")
    resp = client.get(
        f"/tasks?assignee_id={users['bob']['id']}", headers=auth_headers(users["alice"]["token"])
    )
    items = resp.get_json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Mine"


def test_filter_unassigned(client, users):
    create_task(client, users["alice"]["token"], title="Unassigned")
    created = create_task(client, users["alice"]["token"], title="Assigned")
    task_id = created.get_json()["id"]
    client.post(
        f"/tasks/{task_id}/assign",
        json={"username": "bob"},
        headers=auth_headers(users["alice"]["token"]),
    )
    resp = client.get("/tasks?unassigned=true", headers=auth_headers(users["alice"]["token"]))
    items = resp.get_json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Unassigned"


def test_filter_by_creator(client, users):
    create_task(client, users["alice"]["token"], title="Alices")
    create_task(client, users["bob"]["token"], title="Bobs")
    resp = client.get(
        f"/tasks?creator_id={users['alice']['id']}", headers=auth_headers(users["alice"]["token"])
    )
    items = resp.get_json()["items"]
    assert [t["title"] for t in items] == ["Alices"]


def test_search_query(client, users):
    create_task(client, users["alice"]["token"], title="Deploy to production")
    create_task(client, users["alice"]["token"], title="Write documentation")
    create_task(client, users["alice"]["token"], title="Prod monitoring", description="deployment health")
    resp = client.get("/tasks?q=prod", headers=auth_headers(users["alice"]["token"]))
    titles = {t["title"] for t in resp.get_json()["items"]}
    assert titles == {"Deploy to production", "Prod monitoring"}


def test_filter_due_before_and_after(client, users):
    create_task(client, users["alice"]["token"], title="Past", due_date="2026-01-01")
    create_task(client, users["alice"]["token"], title="Middle", due_date="2026-06-15")
    create_task(client, users["alice"]["token"], title="Future", due_date="2026-12-31")

    resp = client.get(
        "/tasks?due_before=2026-06-01", headers=auth_headers(users["alice"]["token"])
    )
    assert [t["title"] for t in resp.get_json()["items"]] == ["Past"]

    resp = client.get(
        "/tasks?due_after=2026-06-01", headers=auth_headers(users["alice"]["token"])
    )
    assert {t["title"] for t in resp.get_json()["items"]} == {"Middle", "Future"}


def test_sort_by_due_date(client, users):
    create_task(client, users["alice"]["token"], title="Later", due_date="2026-12-01")
    create_task(client, users["alice"]["token"], title="Earlier", due_date="2026-01-01")
    create_task(client, users["alice"]["token"], title="No date")
    resp = client.get(
        "/tasks?sort=due_date&sort_dir=asc", headers=auth_headers(users["alice"]["token"])
    )
    assert [t["title"] for t in resp.get_json()["items"]] == ["Earlier", "Later", "No date"]


def test_sort_by_title_desc(client, users):
    create_task(client, users["alice"]["token"], title="Alpha")
    create_task(client, users["alice"]["token"], title="Zulu")
    create_task(client, users["alice"]["token"], title="Mike")
    resp = client.get(
        "/tasks?sort=title&sort_dir=desc", headers=auth_headers(users["alice"]["token"])
    )
    assert [t["title"] for t in resp.get_json()["items"]] == ["Zulu", "Mike", "Alpha"]


def test_sort_by_priority(client, users, priority_ids):
    create_task(client, users["alice"]["token"], title="Medium", priority_id=priority_ids["medium"])
    create_task(client, users["alice"]["token"], title="Urgent", priority_id=priority_ids["urgent"])
    create_task(client, users["alice"]["token"], title="Low", priority_id=priority_ids["low"])
    resp = client.get(
        "/tasks?sort=priority&sort_dir=asc", headers=auth_headers(users["alice"]["token"])
    )
    assert [t["title"] for t in resp.get_json()["items"]] == ["Low", "Medium", "Urgent"]


def test_sort_invalid_field(client, users):
    create_task(client, users["alice"]["token"], title="A")
    resp = client.get(
        "/tasks?sort=banana", headers=auth_headers(users["alice"]["token"])
    )
    assert resp.status_code == 400


def test_sort_invalid_direction(client, users):
    create_task(client, users["alice"]["token"], title="A")
    resp = client.get(
        "/tasks?sort=title&sort_dir=sideways", headers=auth_headers(users["alice"]["token"])
    )
    assert resp.status_code == 400


def test_combined_filters(client, users, priority_ids, category_ids):
    create_task(
        client, users["alice"]["token"], title="Match",
        status="in_progress", priority_id=priority_ids["high"], category_id=category_ids["Work"],
        due_date="2026-09-01",
    )
    create_task(
        client, users["alice"]["token"], title="Mismatch status",
        status="pending", priority_id=priority_ids["high"], category_id=category_ids["Work"],
    )
    create_task(
        client, users["alice"]["token"], title="Mismatch priority",
        status="in_progress", priority_id=priority_ids["low"], category_id=category_ids["Work"],
    )
    resp = client.get(
        "/tasks?status=in_progress&priority=high&category=Work",
        headers=auth_headers(users["alice"]["token"]),
    )
    assert [t["title"] for t in resp.get_json()["items"]] == ["Match"]


def test_list_tasks_requires_auth(client):
    assert client.get("/tasks").status_code == 401
