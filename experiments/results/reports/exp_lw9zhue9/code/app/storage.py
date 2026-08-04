import itertools
from typing import Dict, Any, List


class InMemoryStore:
    def __init__(self):
        self._items: Dict[int, Dict[str, Any]] = {}
        self._id_iter = itertools.count(1)

    def list_items(self, offset: int, limit: int) -> List[Dict[str, Any]]:
        items = list(self._items.values())
        return items[offset: offset + limit]

    def count_items(self) -> int:
        return len(self._items)

    def create_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        item_id = next(self._id_iter)
        stored = {"id": item_id, **item}
        self._items[item_id] = stored
        return stored

    def get_item(self, item_id: int) -> Dict[str, Any] | None:
        return self._items.get(item_id)

    def delete_item(self, item_id: int) -> bool:
        return self._items.pop(item_id, None) is not None


store = InMemoryStore()
