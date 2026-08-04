class User:
    # Simple in-memory user store for demonstration
    _store = {
        'admin': {'username': 'admin', 'password': 'secret'}
    }

    def __init__(self, username, password):
        self.username = username
        self.password = password

    @classmethod
    def get(cls, username):
        data = cls._store.get(username)
        if not data:
            return None
        return cls(username=data["username"], password=data["password"])


# Simple in-memory data to demonstrate pagination
ITEMS = [
    {"id": i, "name": f"Item {i}"} for i in range(1, 51)
]
