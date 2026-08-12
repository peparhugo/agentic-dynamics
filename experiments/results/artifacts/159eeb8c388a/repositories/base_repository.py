from abc import ABC, abstractmethod


class BaseRepository(ABC):
    def __init__(self, get_conn):
        self._get_conn = get_conn

    @abstractmethod
    def create(self, **kwargs):
        pass

    @abstractmethod
    def get_by_id(self, **kwargs):
        pass
