from abc import ABC


class BaseRepository(ABC):
    def __init__(self, db):
        self.db = db

    def _row_to_dict(self, row):
        if row is None:
            return None
        return dict(row)

    def _rows_to_dicts(self, rows):
        return [dict(row) for row in rows]
