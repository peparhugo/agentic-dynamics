from conftest import auth


def test_category_crud(client, alice):
    _user, token = alice
    response = client.post("/api/categories", json={"name": "Work"}, headers=auth(token))
    assert response.status_code == 201
    category_id = response.get_json()["id"]

    response = client.get("/api/categories", headers=auth(token))
    assert [category["name"] for category in response.get_json()["items"]] == ["Work"]

    response = client.patch(
        f"/api/categories/{category_id}", json={"name": "Projects"}, headers=auth(token)
    )
    assert response.status_code == 200
    assert response.get_json()["name"] == "Projects"
    assert client.delete(f"/api/categories/{category_id}", headers=auth(token)).status_code == 204
    assert client.get("/api/categories", headers=auth(token)).get_json()["items"] == []


def test_categories_are_unique_per_user_and_private(client, two_users):
    (_alice, alice_token), (_bob, bob_token) = two_users
    assert client.post("/api/categories", json={"name": "Work"}, headers=auth(alice_token)).status_code == 201
    assert client.post("/api/categories", json={"name": "work"}, headers=auth(alice_token)).status_code == 409
    assert client.post("/api/categories", json={"name": "Work"}, headers=auth(bob_token)).status_code == 201
    assert len(client.get("/api/categories", headers=auth(bob_token)).get_json()["items"]) == 1


def test_category_validation_and_ownership(client, two_users):
    (_alice, alice_token), (_bob, bob_token) = two_users
    category = client.post(
        "/api/categories", json={"name": "Private"}, headers=auth(alice_token)
    ).get_json()
    assert client.post("/api/categories", json={"name": " "}, headers=auth(alice_token)).status_code == 400
    assert client.patch(
        f"/api/categories/{category['id']}", json={"name": "Stolen"}, headers=auth(bob_token)
    ).status_code == 404
    assert client.delete(f"/api/categories/{category['id']}", headers=auth(bob_token)).status_code == 404
