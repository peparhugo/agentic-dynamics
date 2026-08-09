from copy import deepcopy

_users: dict[str, dict] = {}
_items: dict[str, dict] = {}
_next_user_id = 1
_next_item_id = 1


def _next_uid():
    global _next_user_id
    uid = str(_next_user_id)
    _next_user_id += 1
    return uid


def _next_iid():
    global _next_item_id
    iid = str(_next_item_id)
    _next_item_id += 1
    return iid


def create_user(username, hashed_password):
    uid = _next_uid()
    user = {"id": uid, "username": username, "password": hashed_password}
    _users[uid] = user
    return deepcopy(user)


def find_user_by_username(username):
    for u in _users.values():
        if u["username"] == username:
            return deepcopy(u)
    return None


def find_user_by_id(user_id):
    u = _users.get(user_id)
    return deepcopy(u) if u else None


def get_all_users():
    return [deepcopy(u) for u in _users.values()]


def create_item(name, description, owner_id):
    iid = _next_iid()
    item = {"id": iid, "name": name, "description": description, "owner_id": owner_id}
    _items[iid] = item
    return deepcopy(item)


def get_item(item_id):
    item = _items.get(item_id)
    return deepcopy(item) if item else None


def get_items_paginated(page, per_page, owner_id=None):
    items = list(_items.values())
    if owner_id is not None:
        items = [i for i in items if i["owner_id"] == owner_id]
    items.sort(key=lambda i: int(i["id"]))

    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = items[start:end]

    return {
        "data": deepcopy(page_items),
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": max(1, (total + per_page - 1) // per_page),
        },
    }


def update_item(item_id, **kwargs):
    item = _items.get(item_id)
    if not item:
        return None
    for k, v in kwargs.items():
        if v is not None:
            item[k] = v
    return deepcopy(item)


def delete_item(item_id):
    item = _items.pop(item_id, None)
    return deepcopy(item) if item else None


def reset_store():
    global _users, _items, _next_user_id, _next_item_id
    _users = {}
    _items = {}
    _next_user_id = 1
    _next_item_id = 1
