import pytest

from tests.conftest import auth_headers


@pytest.fixture()
def category(client, users):
    res = client.post(
        "/categories", json={"name": "Engineering"},
        headers=auth_headers(users["alice_token"]),
    )
    return res.get_json()


@pytest.fixture()
def sample_task(client, users, category):
    res = client.post(
        "/tasks",
        json={
            "title": "Write tests",
            "description": "Cover the suite",
            "status": "in_progress",
            "priority": "high",
            "category_id": category["id"],
            "due_date": "2026-12-31",
            "assignee_id": users["bob"]["id"],
        },
        headers=auth_headers(users["alice_token"]),
    )
    return res.get_json()


class TestCreateTask:
    def test_create_task_full(self, client, users, category):
        res = client.post(
            "/tasks",
            json={
                "title": "Ship release",
                "description": "Cut the tag",
                "priority": "high",
                "category_id": category["id"],
                "due_date": "2026-09-01",
                "assignee_id": users["bob"]["id"],
            },
            headers=auth_headers(users["alice_token"]),
        )
        assert res.status_code == 201
        body = res.get_json()
        assert body["title"] == "Ship release"
        assert body["status"] == "pending"
        assert body["priority"] == "high"
        assert body["category_name"] == "Engineering"
        assert body["assignee_username"] == "bob"
        assert body["creator_username"] == "alice"
        assert body["due_date"] == "2026-09-01"

    def test_create_task_minimal(self, client, users):
        res = client.post(
            "/tasks", json={"title": "Just a title"},
            headers=auth_headers(users["alice_token"]),
        )
        assert res.status_code == 201
        body = res.get_json()
        assert body["title"] == "Just a title"
        assert body["status"] == "pending"
        assert body["priority"] == "medium"
        assert body["description"] == ""
        assert body["category_id"] is None
        assert body["assignee_id"] is None

    def test_create_task_requires_title(self, client, users):
        res = client.post(
            "/tasks", json={}, headers=auth_headers(users["alice_token"])
        )
        assert res.status_code == 400
        assert "title" in res.get_json()["details"]

    def test_create_task_blank_title(self, client, users):
        res = client.post(
            "/tasks", json={"title": "   "},
            headers=auth_headers(users["alice_token"]),
        )
        assert res.status_code == 400
        assert "title" in res.get_json()["details"]

    @pytest.mark.parametrize("bad_status", ["done", "PENDING", "high", ""])
    def test_create_task_invalid_status(self, client, users, bad_status):
        res = client.post(
            "/tasks", json={"title": "t", "status": bad_status},
            headers=auth_headers(users["alice_token"]),
        )
        assert res.status_code == 400
        assert "status" in res.get_json()["details"]

    @pytest.mark.parametrize("bad_priority", ["critical", "High", 1])
    def test_create_task_invalid_priority(self, client, users, bad_priority):
        res = client.post(
            "/tasks", json={"title": "t", "priority": bad_priority},
            headers=auth_headers(users["alice_token"]),
        )
        assert res.status_code == 400
        assert "priority" in res.get_json()["details"]

    def test_create_task_unknown_category(self, client, users):
        res = client.post(
            "/tasks", json={"title": "t", "category_id": 9999},
            headers=auth_headers(users["alice_token"]),
        )
        assert res.status_code == 400
        assert "category_id" in res.get_json()["details"]

    def test_create_task_unknown_assignee(self, client, users):
        res = client.post(
            "/tasks", json={"title": "t", "assignee_id": 9999},
            headers=auth_headers(users["alice_token"]),
        )
        assert res.status_code == 400
        assert "assignee_id" in res.get_json()["details"]

    def test_create_task_invalid_due_date(self, client, users):
        res = client.post(
            "/tasks", json={"title": "t", "due_date": "not-a-date"},
            headers=auth_headers(users["alice_token"]),
        )
        assert res.status_code == 400
        assert "due_date" in res.get_json()["details"]

    def test_create_task_invalid_category_type(self, client, users):
        res = client.post(
            "/tasks", json={"title": "t", "category_id": "abc"},
            headers=auth_headers(users["alice_token"]),
        )
        assert res.status_code == 400
        assert "category_id" in res.get_json()["details"]

    def test_create_task_requires_auth(self, client):
        assert client.post("/tasks", json={"title": "t"}).status_code == 401


class TestReadTask:
    def test_get_task(self, client, users, sample_task):
        res = client.get(
            f"/tasks/{sample_task['id']}", headers=auth_headers(users["alice_token"])
        )
        assert res.status_code == 200
        assert res.get_json()["title"] == "Write tests"

    def test_get_missing_task(self, client, users):
        res = client.get("/tasks/9999", headers=auth_headers(users["alice_token"]))
        assert res.status_code == 404

    def test_get_task_requires_auth(self, client, sample_task):
        assert client.get(f"/tasks/{sample_task['id']}").status_code == 401


class TestUpdateTask:
    def test_put_full_update(self, client, users, sample_task):
        res = client.put(
            f"/tasks/{sample_task['id']}",
            json={
                "title": "Rewritten",
                "description": "New description",
                "status": "completed",
                "priority": "low",
                "category_id": None,
                "due_date": "2027-01-01",
                "assignee_id": users["alice"]["id"],
            },
            headers=auth_headers(users["alice_token"]),
        )
        assert res.status_code == 200
        body = res.get_json()
        assert body["title"] == "Rewritten"
        assert body["status"] == "completed"
        assert body["priority"] == "low"
        assert body["assignee_username"] == "alice"

    def test_put_requires_title(self, client, users, sample_task):
        res = client.put(
            f"/tasks/{sample_task['id']}", json={"priority": "high"},
            headers=auth_headers(users["alice_token"]),
        )
        assert res.status_code == 400

    def test_patch_updates_status_only(self, client, users, sample_task):
        res = client.patch(
            f"/tasks/{sample_task['id']}", json={"status": "completed"},
            headers=auth_headers(users["alice_token"]),
        )
        assert res.status_code == 200
        body = res.get_json()
        assert body["status"] == "completed"
        assert body["title"] == "Write tests"

    def test_patch_empty_body(self, client, users, sample_task):
        res = client.patch(
            f"/tasks/{sample_task['id']}", json={},
            headers=auth_headers(users["alice_token"]),
        )
        assert res.status_code == 400

    def test_patch_invalid_status(self, client, users, sample_task):
        res = client.patch(
            f"/tasks/{sample_task['id']}", json={"status": "banana"},
            headers=auth_headers(users["alice_token"]),
        )
        assert res.status_code == 400
        assert "status" in res.get_json()["details"]

    def test_patch_clear_assignment(self, client, users, sample_task):
        res = client.patch(
            f"/tasks/{sample_task['id']}", json={"assignee_id": None},
            headers=auth_headers(users["alice_token"]),
        )
        assert res.status_code == 200
        assert res.get_json()["assignee_id"] is None

    def test_update_clears_due_date(self, client, users, sample_task):
        res = client.patch(
            f"/tasks/{sample_task['id']}", json={"due_date": ""},
            headers=auth_headers(users["alice_token"]),
        )
        assert res.status_code == 200
        assert res.get_json()["due_date"] is None

    def test_update_missing_task(self, client, users):
        res = client.put(
            "/tasks/9999", json={"title": "x"},
            headers=auth_headers(users["alice_token"]),
        )
        assert res.status_code == 404

    def test_assignee_can_update(self, client, users, sample_task):
        res = client.patch(
            f"/tasks/{sample_task['id']}", json={"status": "completed"},
            headers=auth_headers(users["bob_token"]),
        )
        assert res.status_code == 200

    def test_outsider_cannot_update(self, client, users):
        res = client.post(
            "/auth/register",
            json={"username": "mallory", "email": "mallory@example.com",
                  "password": "secret123"},
        )
        token = client.post(
            "/auth/login", json={"username": "mallory", "password": "secret123"}
        ).get_json()["access_token"]
        task = client.post(
            "/tasks", json={"title": "private"},
            headers=auth_headers(users["alice_token"]),
        ).get_json()
        res = client.patch(
            f"/tasks/{task['id']}", json={"status": "completed"},
            headers=auth_headers(token),
        )
        assert res.status_code == 403
        res = client.delete(
            f"/tasks/{task['id']}", headers=auth_headers(token)
        )
        assert res.status_code == 403


class TestDeleteTask:
    def test_delete_task(self, client, users, sample_task):
        res = client.delete(
            f"/tasks/{sample_task['id']}",
            headers=auth_headers(users["alice_token"]),
        )
        assert res.status_code == 200
        res2 = client.get(
            f"/tasks/{sample_task['id']}",
            headers=auth_headers(users["alice_token"]),
        )
        assert res2.status_code == 404

    def test_delete_missing_task(self, client, users):
        res = client.delete("/tasks/9999", headers=auth_headers(users["alice_token"]))
        assert res.status_code == 404


class TestPagination:
    def _create_many(self, client, users, n=25):
        created = []
        for i in range(n):
            res = client.post(
                "/tasks", json={"title": f"Task {i:02d}"},
                headers=auth_headers(users["alice_token"]),
            )
            created.append(res.get_json())
        return created

    def test_pagination_default_page_size(self, client, users):
        self._create_many(client, users, n=25)
        res = client.get("/tasks", headers=auth_headers(users["alice_token"]))
        body = res.get_json()
        assert body["total"] == 25
        assert body["page"] == 1
        assert body["per_page"] == 20
        assert body["pages"] == 2
        assert len(body["items"]) == 20

    def test_pagination_second_page(self, client, users):
        self._create_many(client, users, n=25)
        res = client.get(
            "/tasks?page=2&per_page=20",
            headers=auth_headers(users["alice_token"]),
        )
        body = res.get_json()
        assert body["page"] == 2
        assert len(body["items"]) == 5

    def test_pagination_custom_per_page(self, client, users):
        self._create_many(client, users, n=10)
        res = client.get(
            "/tasks?per_page=5", headers=auth_headers(users["alice_token"])
        )
        body = res.get_json()
        assert len(body["items"]) == 5
        assert body["pages"] == 2

    def test_pagination_page_out_of_range(self, client, users):
        self._create_many(client, users, n=5)
        res = client.get(
            "/tasks?page=10", headers=auth_headers(users["alice_token"])
        )
        body = res.get_json()
        assert body["items"] == []
        assert body["total"] == 5

    def test_pagination_invalid_page(self, client, users):
        res = client.get(
            "/tasks?page=0", headers=auth_headers(users["alice_token"])
        )
        assert res.status_code == 400

    def test_pagination_invalid_per_page(self, client, users):
        res = client.get(
            "/tasks?per_page=500", headers=auth_headers(users["alice_token"])
        )
        assert res.status_code == 400

    def test_pagination_non_integer_page(self, client, users):
        res = client.get(
            "/tasks?page=abc", headers=auth_headers(users["alice_token"])
        )
        assert res.status_code == 400


class TestFiltering:
    def _seed(self, client, users, category):
        client.post(
            "/tasks",
            json={"title": "Backend bug fix", "status": "completed",
                  "priority": "high", "category_id": category["id"],
                  "assignee_id": users["bob"]["id"]},
            headers=auth_headers(users["alice_token"]),
        )
        client.post(
            "/tasks",
            json={"title": "Frontend polish", "status": "in_progress",
                  "priority": "medium", "category_id": category["id"]},
            headers=auth_headers(users["alice_token"]),
        )
        client.post(
            "/tasks",
            json={"title": "Docs update", "status": "pending", "priority": "low"},
            headers=auth_headers(users["bob_token"]),
        )

    def test_filter_by_status(self, client, users, category):
        self._seed(client, users, category)
        res = client.get(
            "/tasks?status=completed", headers=auth_headers(users["alice_token"])
        )
        body = res.get_json()
        assert body["total"] == 1
        assert body["items"][0]["title"] == "Backend bug fix"

    def test_filter_by_priority(self, client, users, category):
        self._seed(client, users, category)
        res = client.get(
            "/tasks?priority=medium", headers=auth_headers(users["alice_token"])
        )
        body = res.get_json()
        assert body["total"] == 1
        assert body["items"][0]["title"] == "Frontend polish"

    def test_filter_by_category(self, client, users, category):
        self._seed(client, users, category)
        res = client.get(
            f"/tasks?category_id={category['id']}",
            headers=auth_headers(users["alice_token"]),
        )
        assert res.get_json()["total"] == 2

    def test_filter_by_assignee(self, client, users, category):
        self._seed(client, users, category)
        res = client.get(
            f"/tasks?assignee_id={users['bob']['id']}",
            headers=auth_headers(users["alice_token"]),
        )
        assert res.get_json()["total"] == 1

    def test_filter_invalid_status(self, client, users):
        res = client.get(
            "/tasks?status=bad", headers=auth_headers(users["alice_token"])
        )
        assert res.status_code == 400

    def test_filter_invalid_priority(self, client, users):
        res = client.get(
            "/tasks?priority=bad", headers=auth_headers(users["alice_token"])
        )
        assert res.status_code == 400

    def test_filter_unknown_category(self, client, users):
        res = client.get(
            "/tasks?category_id=9999", headers=auth_headers(users["alice_token"])
        )
        assert res.status_code == 404

    def test_filter_invalid_sort_by(self, client, users):
        res = client.get(
            "/tasks?sort_by=nope", headers=auth_headers(users["alice_token"])
        )
        assert res.status_code == 400

    def test_filter_invalid_sort_order(self, client, users):
        res = client.get(
            "/tasks?sort_order=sideways", headers=auth_headers(users["alice_token"])
        )
        assert res.status_code == 400


class TestSearch:
    def _seed(self, client, users):
        client.post(
            "/tasks", json={"title": "Refactor the auth module"},
            headers=auth_headers(users["alice_token"]),
        )
        client.post(
            "/tasks",
            json={"title": "Set up CI", "description": "Build pipeline automation"},
            headers=auth_headers(users["alice_token"]),
        )

    def test_search_by_title(self, client, users):
        self._seed(client, users)
        res = client.get(
            "/tasks?search=auth", headers=auth_headers(users["alice_token"])
        )
        assert res.get_json()["total"] == 1

    def test_search_by_description(self, client, users):
        self._seed(client, users)
        res = client.get(
            "/tasks?search=pipeline", headers=auth_headers(users["alice_token"])
        )
        assert res.get_json()["total"] == 1

    def test_search_case_insensitive(self, client, users):
        self._seed(client, users)
        res = client.get(
            "/tasks?search=AUTH", headers=auth_headers(users["alice_token"])
        )
        assert res.get_json()["total"] == 1

    def test_search_no_match(self, client, users):
        self._seed(client, users)
        res = client.get(
            "/tasks?search=zzzz", headers=auth_headers(users["alice_token"])
        )
        assert res.get_json()["total"] == 0


class TestSorting:
    def test_sort_by_due_date_asc(self, client, users):
        client.post(
            "/tasks", json={"title": "Later", "due_date": "2026-12-01"},
            headers=auth_headers(users["alice_token"]),
        )
        client.post(
            "/tasks", json={"title": "Earlier", "due_date": "2026-01-01"},
            headers=auth_headers(users["alice_token"]),
        )
        res = client.get(
            "/tasks?sort_by=due_date&sort_order=asc",
            headers=auth_headers(users["alice_token"]),
        )
        items = res.get_json()["items"]
        assert items[0]["title"] == "Earlier"
        assert items[1]["title"] == "Later"

    def test_sort_by_priority_desc(self, client, users):
        client.post(
            "/tasks", json={"title": "Low", "priority": "low"},
            headers=auth_headers(users["alice_token"]),
        )
        client.post(
            "/tasks", json={"title": "High", "priority": "high"},
            headers=auth_headers(users["alice_token"]),
        )
        client.post(
            "/tasks", json={"title": "Medium", "priority": "medium"},
            headers=auth_headers(users["alice_token"]),
        )
        res = client.get(
            "/tasks?sort_by=priority&sort_order=desc",
            headers=auth_headers(users["alice_token"]),
        )
        titles = [t["title"] for t in res.get_json()["items"]]
        assert titles == ["High", "Medium", "Low"]

    def test_default_sort_created_desc(self, client, users):
        first = client.post(
            "/tasks", json={"title": "First"},
            headers=auth_headers(users["alice_token"]),
        ).get_json()
        second = client.post(
            "/tasks", json={"title": "Second"},
            headers=auth_headers(users["alice_token"]),
        ).get_json()
        res = client.get("/tasks", headers=auth_headers(users["alice_token"]))
        titles = [t["title"] for t in res.get_json()["items"]]
        assert titles == [second["title"], first["title"]]


class TestStats:
    def test_stats_counts(self, client, users):
        client.post(
            "/tasks", json={"title": "A", "status": "pending", "priority": "low"},
            headers=auth_headers(users["alice_token"]),
        )
        client.post(
            "/tasks", json={"title": "B", "status": "completed", "priority": "high"},
            headers=auth_headers(users["alice_token"]),
        )
        client.post(
            "/tasks", json={"title": "C", "status": "completed", "priority": "high"},
            headers=auth_headers(users["bob_token"]),
        )
        res = client.get("/tasks/stats", headers=auth_headers(users["alice_token"]))
        body = res.get_json()
        assert body["total"] == 3
        assert body["by_status"] == {"pending": 1, "completed": 2}
        assert body["by_priority"] == {"low": 1, "high": 2}
