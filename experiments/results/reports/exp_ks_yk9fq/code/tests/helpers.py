def register_user(client, username="alice", email="alice@example.com", password="password123"):
    return client.post(
        "/api/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def login(client, identifier, password):
    return client.post(
        "/api/auth/login",
        json={"username": identifier, "password": password},
    )
