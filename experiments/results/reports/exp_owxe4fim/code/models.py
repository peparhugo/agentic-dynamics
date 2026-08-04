import uuid
import threading

class InMemoryStore:
    def __init__(self):
        self._lock = threading.Lock()
        self.users = {}
        self.items = {}

    def create_user(self, username, password_hash):
        with self._lock:
            self.users[username] = {'username': username, 'password': password_hash}
            return self.users[username]

    def get_user(self, username):
        return self.users.get(username)

    def create_item(self, data):
        with self._lock:
            item_id = str(uuid.uuid4())
            item = {'id': item_id, 'name': data['name'], 'value': data.get('value')}
            self.items[item_id] = item
            return item

    def get_item(self, item_id):
        return self.items.get(item_id)

    def list_items(self, page=1, per_page=10):
        all_items = list(self.items.values())
        total = len(all_items)
        start = (page - 1) * per_page
        end = start + per_page
        return all_items[start:end], total
