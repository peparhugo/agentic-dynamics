import pytest


def create_category(client, headers, name="Work"):
    resp = client.post("/api/categories", json={"name": name}, headers=headers)
    return resp.get_json()["category"]["id"]


def create_task(client, headers, **overrides):
    payload = {"title": "Default task"}
    payload.update(overrides)
    return client.post("/api/tasks", json=payload, headers=headers)


class TestTaskCreate:
    def test_create_task_minimal(self, client, user_alice):
        resp = create_task(client, user_alice["headers"], title="Write report")
        assert resp.status_code == 201
        data = resp.get_json()["task"]
        assert data["title"] == "Write report"
        assert data["status"] == "pending"
        assert data["priority"] == "medium"
        assert data["owner_id"] == user_alice["user"]["id"]
        assert data["assignee_id"] is None

    def test_create_task_requires_auth(self, client):
        resp = client.post("/api/tasks", json={"title": "x"})
        assert resp.status_code == 401

    def test_create_task_requires_title(self, client, user_alice):
        resp = create_task(client, user_alice["headers"], title="")
        assert resp.status_code == 400
        assert "title" in resp.get_json()["details"]

    def test_create_task_with_full_fields(self, client, user_alice, user_bob):
        category_id = create_category(client, user_alice["headers"])
        resp = create_task(
            client,
            user_alice["headers"],
            title="Ship feature",
            description="Ship the new feature end to end",
            status="in_progress",
            priority="high",
            due_date="2026-12-31T23:59:59",
            category_id=category_id,
            assignee_id=user_bob["user"]["id"],
        )
        assert resp.status_code == 201
        data = resp.get_json()["task"]
        assert data["status"] == "in_progress"
        assert data["priority"] == "high"
        assert data["category_id"] == category_id
        assert data["assignee_id"] == user_bob["user"]["id"]
        assert data["due_date"].startswith("2026-12-31T23:59:59")

    def test_create_task_invalid_status(self, client, user_alice):
        resp = create_task(client, user_alice["headers"], status="bogus")
        assert resp.status_code == 400

    def test_create_task_invalid_priority(self, client, user_alice):
        resp = create_task(client, user_alice["headers"], priority="bogus")
        assert resp.status_code == 400

    def test_create_task_invalid_due_date(self, client, user_alice):
        resp = create_task(client, user_alice["headers"], due_date="not-a-date")
        assert resp.status_code == 400

    def test_create_task_invalid_category(self, client, user_alice):
        resp = create_task(client, user_alice["headers"], category_id=999)
        assert resp.status_code == 400

    def test_create_task_category_owned_by_other_user_rejected(
        self, client, user_alice, user_bob
    ):
        category_id = create_category(client, user_bob["headers"])
        resp = create_task(client, user_alice["headers"], category_id=category_id)
        assert resp.status_code == 400

    def test_create_task_invalid_assignee(self, client, user_alice):
        resp = create_task(client, user_alice["headers"], assignee_id=999)
        assert resp.status_code == 400


class TestTaskReadAndPermissions:
    def test_get_own_task(self, client, user_alice):
        created = create_task(client, user_alice["headers"]).get_json()["task"]
        resp = client.get(f"/api/tasks/{created['id']}", headers=user_alice["headers"])
        assert resp.status_code == 200

    def test_get_task_not_found(self, client, user_alice):
        resp = client.get("/api/tasks/999", headers=user_alice["headers"])
        assert resp.status_code == 404

    def test_get_unrelated_task_forbidden(self, client, user_alice, user_bob):
        created = create_task(client, user_alice["headers"]).get_json()["task"]
        resp = client.get(f"/api/tasks/{created['id']}", headers=user_bob["headers"])
        assert resp.status_code == 403

    def test_assignee_can_view_task(self, client, user_alice, user_bob):
        created = create_task(
            client, user_alice["headers"], assignee_id=user_bob["user"]["id"]
        ).get_json()["task"]
        resp = client.get(f"/api/tasks/{created['id']}", headers=user_bob["headers"])
        assert resp.status_code == 200


class TestTaskUpdate:
    def test_owner_can_update_any_field(self, client, user_alice):
        created = create_task(client, user_alice["headers"]).get_json()["task"]
        resp = client.put(
            f"/api/tasks/{created['id']}",
            json={"title": "Updated title", "priority": "urgent", "status": "completed"},
            headers=user_alice["headers"],
        )
        assert resp.status_code == 200
        data = resp.get_json()["task"]
        assert data["title"] == "Updated title"
        assert data["priority"] == "urgent"
        assert data["status"] == "completed"

    def test_update_requires_auth(self, client, user_alice):
        created = create_task(client, user_alice["headers"]).get_json()["task"]
        resp = client.put(f"/api/tasks/{created['id']}", json={"title": "x"})
        assert resp.status_code == 401

    def test_unrelated_user_cannot_update(self, client, user_alice, user_bob):
        created = create_task(client, user_alice["headers"]).get_json()["task"]
        resp = client.put(
            f"/api/tasks/{created['id']}",
            json={"title": "hacked"},
            headers=user_bob["headers"],
        )
        assert resp.status_code == 403

    def test_assignee_can_update_status_only(self, client, user_alice, user_bob):
        created = create_task(
            client, user_alice["headers"], assignee_id=user_bob["user"]["id"]
        ).get_json()["task"]

        resp = client.put(
            f"/api/tasks/{created['id']}",
            json={"status": "in_progress"},
            headers=user_bob["headers"],
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["status"] == "in_progress"

    def test_assignee_cannot_update_title(self, client, user_alice, user_bob):
        created = create_task(
            client, user_alice["headers"], assignee_id=user_bob["user"]["id"]
        ).get_json()["task"]

        resp = client.put(
            f"/api/tasks/{created['id']}",
            json={"title": "sneaky change"},
            headers=user_bob["headers"],
        )
        assert resp.status_code == 403

    def test_update_invalid_status_rejected(self, client, user_alice):
        created = create_task(client, user_alice["headers"]).get_json()["task"]
        resp = client.put(
            f"/api/tasks/{created['id']}",
            json={"status": "bogus"},
            headers=user_alice["headers"],
        )
        assert resp.status_code == 400

    def test_reassign_task(self, client, user_alice, user_bob):
        created = create_task(client, user_alice["headers"]).get_json()["task"]
        resp = client.put(
            f"/api/tasks/{created['id']}",
            json={"assignee_id": user_bob["user"]["id"]},
            headers=user_alice["headers"],
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["assignee_id"] == user_bob["user"]["id"]

    def test_unassign_task(self, client, user_alice, user_bob):
        created = create_task(
            client, user_alice["headers"], assignee_id=user_bob["user"]["id"]
        ).get_json()["task"]
        resp = client.put(
            f"/api/tasks/{created['id']}",
            json={"assignee_id": None},
            headers=user_alice["headers"],
        )
        assert resp.status_code == 200
        assert resp.get_json()["task"]["assignee_id"] is None


class TestTaskDelete:
    def test_owner_can_delete(self, client, user_alice):
        created = create_task(client, user_alice["headers"]).get_json()["task"]
        resp = client.delete(f"/api/tasks/{created['id']}", headers=user_alice["headers"])
        assert resp.status_code == 200
        assert client.get(
            f"/api/tasks/{created['id']}", headers=user_alice["headers"]
        ).status_code == 404

    def test_assignee_cannot_delete(self, client, user_alice, user_bob):
        created = create_task(
            client, user_alice["headers"], assignee_id=user_bob["user"]["id"]
        ).get_json()["task"]
        resp = client.delete(f"/api/tasks/{created['id']}", headers=user_bob["headers"])
        assert resp.status_code == 403

    def test_unrelated_user_cannot_delete(self, client, user_alice, user_bob):
        created = create_task(client, user_alice["headers"]).get_json()["task"]
        resp = client.delete(f"/api/tasks/{created['id']}", headers=user_bob["headers"])
        assert resp.status_code == 403

    def test_delete_requires_auth(self, client, user_alice):
        created = create_task(client, user_alice["headers"]).get_json()["task"]
        resp = client.delete(f"/api/tasks/{created['id']}")
        assert resp.status_code == 401


class TestTaskListPaginationSearchFilter:
    @pytest.fixture()
    def seeded(self, client, user_alice, user_bob):
        work = create_category(client, user_alice["headers"], "Work")
        personal = create_category(client, user_alice["headers"], "Personal")

        specs = [
            dict(title="Write quarterly report", status="pending", priority="high",
                 category_id=work),
            dict(title="Refactor billing module", status="in_progress", priority="high",
                 category_id=work),
            dict(title="Buy groceries", status="pending", priority="low",
                 category_id=personal),
            dict(title="Plan birthday party", status="completed", priority="medium",
                 category_id=personal),
            dict(title="Review pull requests", status="pending", priority="urgent",
                 category_id=work, assignee_id=user_bob["user"]["id"]),
            dict(title="Clean garage", status="cancelled", priority="low",
                 category_id=personal),
        ]
        for spec in specs:
            create_task(client, user_alice["headers"], **spec)

        return {"work": work, "personal": personal}

    def test_list_requires_auth(self, client):
        resp = client.get("/api/tasks")
        assert resp.status_code == 401

    def test_list_returns_only_owned_or_assigned(self, client, user_alice, user_bob, seeded):
        resp = client.get("/api/tasks", headers=user_bob["headers"])
        data = resp.get_json()
        assert data["pagination"]["total_items"] == 1
        assert data["items"][0]["title"] == "Review pull requests"

    def test_pagination_defaults(self, client, user_alice, seeded):
        resp = client.get("/api/tasks", headers=user_alice["headers"])
        data = resp.get_json()
        assert data["pagination"]["total_items"] == 6
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 10
        assert data["pagination"]["total_pages"] == 1
        assert len(data["items"]) == 6

    def test_pagination_custom_page_size(self, client, user_alice, seeded):
        resp = client.get("/api/tasks?per_page=2&page=1", headers=user_alice["headers"])
        data = resp.get_json()
        assert len(data["items"]) == 2
        assert data["pagination"]["total_pages"] == 3
        assert data["pagination"]["has_next"] is True
        assert data["pagination"]["has_prev"] is False

    def test_pagination_second_page(self, client, user_alice, seeded):
        resp = client.get("/api/tasks?per_page=2&page=2", headers=user_alice["headers"])
        data = resp.get_json()
        assert len(data["items"]) == 2
        assert data["pagination"]["has_prev"] is True

    def test_pagination_page_beyond_range_returns_empty(self, client, user_alice, seeded):
        resp = client.get("/api/tasks?per_page=2&page=99", headers=user_alice["headers"])
        data = resp.get_json()
        assert data["items"] == []

    def test_pagination_caps_per_page(self, client, user_alice, seeded):
        resp = client.get("/api/tasks?per_page=1000", headers=user_alice["headers"])
        data = resp.get_json()
        assert data["pagination"]["per_page"] == 100

    def test_filter_by_status(self, client, user_alice, seeded):
        resp = client.get("/api/tasks?status=pending", headers=user_alice["headers"])
        data = resp.get_json()
        assert data["pagination"]["total_items"] == 3
        assert all(t["status"] == "pending" for t in data["items"])

    def test_filter_by_invalid_status(self, client, user_alice, seeded):
        resp = client.get("/api/tasks?status=bogus", headers=user_alice["headers"])
        assert resp.status_code == 400

    def test_filter_by_priority(self, client, user_alice, seeded):
        resp = client.get("/api/tasks?priority=high", headers=user_alice["headers"])
        data = resp.get_json()
        assert data["pagination"]["total_items"] == 2
        assert all(t["priority"] == "high" for t in data["items"])

    def test_filter_by_category(self, client, user_alice, seeded):
        resp = client.get(
            f"/api/tasks?category_id={seeded['personal']}", headers=user_alice["headers"]
        )
        data = resp.get_json()
        assert data["pagination"]["total_items"] == 3
        assert all(t["category_id"] == seeded["personal"] for t in data["items"])

    def test_filter_combined(self, client, user_alice, seeded):
        resp = client.get(
            f"/api/tasks?category_id={seeded['work']}&status=pending",
            headers=user_alice["headers"],
        )
        data = resp.get_json()
        titles = {t["title"] for t in data["items"]}
        assert titles == {"Write quarterly report", "Review pull requests"}

    def test_search_by_title(self, client, user_alice, seeded):
        resp = client.get("/api/tasks?q=report", headers=user_alice["headers"])
        data = resp.get_json()
        assert data["pagination"]["total_items"] == 1
        assert data["items"][0]["title"] == "Write quarterly report"

    def test_search_case_insensitive(self, client, user_alice, seeded):
        resp = client.get("/api/tasks?q=GARAGE", headers=user_alice["headers"])
        data = resp.get_json()
        assert data["pagination"]["total_items"] == 1

    def test_search_no_match(self, client, user_alice, seeded):
        resp = client.get("/api/tasks?q=nonexistentterm", headers=user_alice["headers"])
        data = resp.get_json()
        assert data["pagination"]["total_items"] == 0
        assert data["items"] == []

    def test_sort_by_title_ascending(self, client, user_alice, seeded):
        resp = client.get(
            "/api/tasks?sort_by=title&sort_dir=asc", headers=user_alice["headers"]
        )
        titles = [t["title"] for t in resp.get_json()["items"]]
        assert titles == sorted(titles)
