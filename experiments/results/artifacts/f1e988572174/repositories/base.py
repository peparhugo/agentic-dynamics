from abc import ABC, abstractmethod
import sqlite3
from typing import Callable


class BaseRepository(ABC):
    def __init__(self, db_getter: Callable[[], sqlite3.Connection]):
        self._get_db = db_getter
