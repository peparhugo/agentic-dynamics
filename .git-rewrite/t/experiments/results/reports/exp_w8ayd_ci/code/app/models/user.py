from werkzeug.security import generate_password_hash, check_password_hash


class User:
    def __init__(self, id, username, password_hash, roles=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.roles = roles or ["user"]

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "roles": self.roles,
        }


_USERS = {
    "admin": User(
        id=1,
        username="admin",
        password_hash=generate_password_hash("admin123"),
        roles=["admin", "user"],
    ),
    "user": User(
        id=2,
        username="user",
        password_hash=generate_password_hash("user123"),
        roles=["user"],
    ),
}


def get_user_by_username(username):
    return _USERS.get(username)


def get_user_by_id(user_id):
    for user in _USERS.values():
        if user.id == user_id:
            return user
    return None
