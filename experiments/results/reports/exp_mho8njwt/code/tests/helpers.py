import json


def register_user(client, username="testuser", password="password123"):
    return client.post(
        "/v1/auth/register",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def login_user(client, username="testuser", password="password123"):
    return client.post(
        "/v1/auth/login",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def get_auth_header(client):
    login_resp = login_user(client)
    tokens = login_resp.get_json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}
