class TestInputValidation:
    def test_register_empty_body(self, client):
        resp = client.post("/api/v1/auth/register", json={})
        assert resp.status_code == 422

    def test_register_null_body(self, client):
        resp = client.post("/api/v1/auth/register", data=None,
                           headers={"Content-Type": "application/json"})
        assert resp.status_code == 422

    def test_login_empty_body(self, client):
        resp = client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422

    def test_create_widget_empty_name(self, client, auth_header):
        resp = client.post("/api/v1/widgets", headers=auth_header, json={
            "name": ""
        })
        assert resp.status_code == 422

    def test_create_widget_missing_name(self, client, auth_header):
        resp = client.post("/api/v1/widgets", headers=auth_header, json={
            "description": "no name here"
        })
        assert resp.status_code == 422

    def test_create_widget_name_too_long(self, client, auth_header):
        resp = client.post("/api/v1/widgets", headers=auth_header, json={
            "name": "x" * 300
        })
        assert resp.status_code == 422

    def test_pagination_bad_params(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "name": "P", "email": "p@test.com", "password": "secret123"
        })
        token = resp.get_json()["token"]
        h = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/v1/widgets?page=-1", headers=h)
        assert resp.status_code == 400

        resp = client.get("/api/v1/widgets?page=0", headers=h)
        assert resp.status_code == 400

        resp = client.get("/api/v1/widgets?per_page=999", headers=h)
        assert resp.status_code == 400
