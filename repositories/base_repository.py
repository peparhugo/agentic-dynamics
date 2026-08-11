from abc import ABC, abstractmethod


class BaseRepository(ABC):
    def __init__(self, db_connection):
        self._connection = db_connection

    def _get_db(self):
        return self._connection()

    @abstractmethod
    def create(self, *args, **kwargs):
        ...

    @abstractmethod
    def find_by_id(self, *args, **kwargs):
        ...
