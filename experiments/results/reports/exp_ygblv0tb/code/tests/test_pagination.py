def _seed_notes(client, headers, count):
    for i in range(count):
        resp = client.post("/api/v1/notes",
                           json={"title": f"note-{i:03d}"}, headers=headers)
        assert resp.status_code == 201


class TestPagination:
    def test_default_page_size(self, client, auth_headers, app):
        _seed_notes(client, auth_headers, 25)
        resp = client.get("/api/v1/notes", headers=auth_headers)
        body = resp.get_json()
        assert len(body["items"]) == app.config["DEFAULT_PAGE_SIZE"]
        assert body["pagination"]["total_items"] == 25
        assert body["pagination"]["total_pages"] == 2

    def test_explicit_page_and_per_page(self, client, auth_headers):
        _seed_notes(client, auth_headers, 12)
        resp = client.get("/api/v1/notes?page=2&per_page=5",
                          headers=auth_headers)
        body = resp.get_json()
        assert len(body["items"]) == 5
        assert body["pagination"]["page"] == 2
        assert body["pagination"]["per_page"] == 5

    def test_navigation_links(self, client, auth_headers):
        _seed_notes(client, auth_headers, 12)
        body = client.get("/api/v1/notes?page=2&per_page=5",
                          headers=auth_headers).get_json()
        assert "page=3" in body["pagination"]["next"]
        assert "page=1" in body["pagination"]["prev"]

        first = client.get("/api/v1/notes?page=1&per_page=5",
                           headers=auth_headers).get_json()
        assert first["pagination"]["prev"] is None

        last = client.get("/api/v1/notes?page=3&per_page=5",
                          headers=auth_headers).get_json()
        assert last["pagination"]["next"] is None

    def test_per_page_capped_at_max(self, client, auth_headers, app):
        _seed_notes(client, auth_headers, 1)
        resp = client.get("/api/v1/notes?per_page=999", headers=auth_headers)
        assert resp.get_json()["pagination"]["per_page"] == \
            app.config["MAX_PAGE_SIZE"]

    def test_invalid_page_param(self, client, auth_headers):
        resp = client.get("/api/v1/notes?page=0", headers=auth_headers)
        assert resp.status_code == 400
        resp = client.get("/api/v1/notes?page=banana", headers=auth_headers)
        assert resp.status_code == 400

    def test_page_past_end_is_empty(self, client, auth_headers):
        _seed_notes(client, auth_headers, 3)
        body = client.get("/api/v1/notes?page=50", headers=auth_headers).get_json()
        assert body["items"] == []

    def test_ordering_newest_first(self, client, auth_headers):
        _seed_notes(client, auth_headers, 3)
        titles = [n["title"] for n in
                  client.get("/api/v1/notes", headers=auth_headers)
                  .get_json()["items"]]
        assert titles == ["note-002", "note-001", "note-000"]
