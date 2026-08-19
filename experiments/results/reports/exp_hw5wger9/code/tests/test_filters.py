def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _post(client, token, **fields):
    return client.post("/api/tasks", json=fields, headers=_headers(token))


def _get_ids(client, token, url="/api/tasks"):
    resp = client.get(url, headers=_headers(token))
    assert resp.status_code == 200
    return [t["id"] for t in resp.get_json()["tasks"]]


def test_filter_by_status(client, make_user):
    user = make_user()
    _post(client, user["token"], title="a", status="todo")
    done = _post(client, user["token"], title="b", status="done").get_json()["task"]
    _post(client, user["token"], title="c", status="in_progress")

    ids = _get_ids(client, user["token"], "/api/tasks?status=done")
    assert ids == [done["id"]]


def test_filter_by_invalid_status(client, make_user):
    user = make_user()
    resp = client.get("/api/tasks?status=unknown", headers=_headers(user["token"]))
    assert resp.status_code == 400


def test_filter_by_priority(client, make_user):
    user = make_user()
    high = _post(client, user["token"], title="h", priority="high").get_json()["task"]
    _post(client, user["token"], title="l", priority="low")

    ids = _get_ids(client, user["token"], "/api/tasks?priority=high")
    assert ids == [high["id"]]


def test_filter_by_category_id(client, make_user, make_category):
    category, headers = make_category("Work")
    user = make_user("alice")
    _post(client, user["token"], title="x", category_id=category["id"])
    _post(client, user["token"], title="y")

    ids = _get_ids(client, user["token"], f"/api/tasks?category_id={category['id']}")
    assert len(ids) == 1


def test_filter_by_category_name(client, make_user, make_category):
    make_category("Work")
    user = make_user("alice")
    resp = _post(
        client, user["token"], title="x", category_id=1
    )
    _post(client, user["token"], title="y")
    ids = _get_ids(client, user["token"], "/api/tasks?category=Work")
    assert ids == [resp.get_json()["task"]["id"]]


def test_filter_by_assignee(client, make_user):
    user = make_user("alice")
    bob = make_user("bob")
    assigned = _post(client, user["token"], title="x", assignee_id=bob["user"]["id"]).get_json()["task"]
    _post(client, user["token"], title="y")

    ids = _get_ids(client, user["token"], f"/api/tasks?assignee_id={bob['user']['id']}")
    assert ids == [assigned["id"]]

    ids = _get_ids(client, user["token"], "/api/tasks?assignee=bob")
    assert ids == [assigned["id"]]


def test_search_by_title(client, make_user):
    user = make_user()
    _post(client, user["token"], title="Buy groceries")
    target = _post(client, user["token"], title="Write report").get_json()["task"]
    _post(client, user["token"], title="Fix bug")

    ids = _get_ids(client, user["token"], "/api/tasks?q=report")
    assert ids == [target["id"]]


def test_search_by_description(client, make_user):
    user = make_user()
    target = _post(client, user["token"], title="A", description="contains needle").get_json()["task"]
    _post(client, user["token"], title="B", description="nothing")

    ids = _get_ids(client, user["token"], "/api/tasks?q=needle")
    assert ids == [target["id"]]


def test_search_is_case_insensitive(client, make_user):
    user = make_user()
    target = _post(client, user["token"], title="Report").get_json()["task"]
    ids = _get_ids(client, user["token"], "/api/tasks?q=REPORT")
    assert ids == [target["id"]]


def test_combined_filters(client, make_user, make_category):
    make_category("Work")
    user = make_user("alice")
    target = _post(
        client,
        user["token"],
        title="Urgent work task",
        status="todo",
        priority="urgent",
        category_id=1,
    ).get_json()["task"]
    _post(client, user["token"], title="done work", status="done", priority="urgent", category_id=1)
    _post(client, user["token"], title="todo personal", status="todo", priority="low")

    ids = _get_ids(
        client,
        user["token"],
        "/api/tasks?status=todo&priority=urgent&category=Work&q=work",
    )
    assert ids == [target["id"]]


def test_sort_by_priority(client, make_user):
    user = make_user()
    low = _post(client, user["token"], title="low", priority="low").get_json()["task"]
    urgent = _post(client, user["token"], title="urgent", priority="urgent").get_json()["task"]
    high = _post(client, user["token"], title="high", priority="high").get_json()["task"]

    ids = _get_ids(client, user["token"], "/api/tasks?sort_by=priority&order=asc")
    assert ids == [urgent["id"], high["id"], low["id"]]


def test_sort_by_due_date(client, make_user):
    user = make_user()
    late = _post(client, user["token"], title="late", due_date="2026-12-31").get_json()["task"]
    early = _post(client, user["token"], title="early", due_date="2026-01-01").get_json()["task"]

    ids = _get_ids(client, user["token"], "/api/tasks?sort_by=due_date&order=asc")
    assert ids == [early["id"], late["id"]]


def test_invalid_sort_field(client, make_user):
    user = make_user()
    resp = client.get("/api/tasks?sort_by=bogus", headers=_headers(user["token"]))
    assert resp.status_code == 400


def test_invalid_sort_order(client, make_user):
    user = make_user()
    resp = client.get("/api/tasks?order=sideways", headers=_headers(user["token"]))
    assert resp.status_code == 400


def test_filter_by_due_date_range(client, make_user):
    user = make_user()
    early = _post(client, user["token"], title="e", due_date="2026-01-01").get_json()["task"]
    mid = _post(client, user["token"], title="m", due_date="2026-06-15").get_json()["task"]
    _post(client, user["token"], title="l", due_date="2026-12-31")

    ids = _get_ids(
        client, user["token"], "/api/tasks?due_after=2026-01-01&due_before=2026-06-30"
    )
    assert sorted(ids) == sorted([early["id"], mid["id"]])
