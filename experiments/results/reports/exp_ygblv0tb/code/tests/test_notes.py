def _create_note(client, headers, title="First note", body="hello"):
    return client.post("/api/v1/notes", json={"title": title, "body": body},
                       headers=headers)


class TestCreate:
    def test_create_note(self, client, auth_headers):
        resp = _create_note(client, auth_headers)
        assert resp.status_code == 201
        note = resp.get_json()["note"]
        assert note["title"] == "First note"
        assert note["body"] == "hello"
        assert note["id"]

    def test_create_requires_auth(self, client):
        resp = client.post("/api/v1/notes", json={"title": "x"})
        assert resp.status_code == 401

    def test_create_missing_title(self, client, auth_headers):
        resp = client.post("/api/v1/notes", json={"body": "no title"},
                           headers=auth_headers)
        assert resp.status_code == 400
        assert "title" in resp.get_json()["error"]["details"]

    def test_create_title_too_long(self, client, auth_headers):
        resp = _create_note(client, auth_headers, title="x" * 201)
        assert resp.status_code == 400

    def test_create_rejects_unknown_fields(self, client, auth_headers):
        resp = client.post("/api/v1/notes",
                           json={"title": "ok", "evil": "field"},
                           headers=auth_headers)
        assert resp.status_code == 400


class TestReadUpdateDelete:
    def test_get_note(self, client, auth_headers):
        note_id = _create_note(client, auth_headers).get_json()["note"]["id"]
        resp = client.get(f"/api/v1/notes/{note_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["note"]["id"] == note_id

    def test_get_missing_note_404(self, client, auth_headers):
        resp = client.get("/api/v1/notes/9999", headers=auth_headers)
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "not_found"

    def test_update_note(self, client, auth_headers):
        note_id = _create_note(client, auth_headers).get_json()["note"]["id"]
        resp = client.patch(f"/api/v1/notes/{note_id}",
                            json={"title": "Renamed"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["note"]["title"] == "Renamed"
        assert resp.get_json()["note"]["body"] == "hello"

    def test_update_empty_payload_rejected(self, client, auth_headers):
        note_id = _create_note(client, auth_headers).get_json()["note"]["id"]
        resp = client.patch(f"/api/v1/notes/{note_id}", json={},
                            headers=auth_headers)
        assert resp.status_code == 400

    def test_delete_note(self, client, auth_headers):
        note_id = _create_note(client, auth_headers).get_json()["note"]["id"]
        resp = client.delete(f"/api/v1/notes/{note_id}", headers=auth_headers)
        assert resp.status_code == 204
        assert client.get(f"/api/v1/notes/{note_id}",
                          headers=auth_headers).status_code == 404


class TestOwnership:
    def test_users_cannot_see_others_notes(self, client, auth_headers,
                                           second_user_headers):
        note_id = _create_note(client, auth_headers).get_json()["note"]["id"]

        # Bob cannot read, update, or delete Alice's note.
        assert client.get(f"/api/v1/notes/{note_id}",
                          headers=second_user_headers).status_code == 404
        assert client.patch(f"/api/v1/notes/{note_id}", json={"title": "hax"},
                            headers=second_user_headers).status_code == 404
        assert client.delete(f"/api/v1/notes/{note_id}",
                             headers=second_user_headers).status_code == 404

    def test_list_only_shows_own_notes(self, client, auth_headers,
                                       second_user_headers):
        _create_note(client, auth_headers, title="alice-note")
        _create_note(client, second_user_headers, title="bob-note")

        titles = [n["title"] for n in
                  client.get("/api/v1/notes", headers=auth_headers)
                  .get_json()["items"]]
        assert titles == ["alice-note"]
