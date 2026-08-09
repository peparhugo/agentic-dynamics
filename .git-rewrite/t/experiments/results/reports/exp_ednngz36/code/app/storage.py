"""Thread-safe in-memory storage.

Deliberately simple: swap for SQLAlchemy/Postgres behind the same interface
without touching route code.
"""
import itertools
import threading
from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc)


class Store:
    def __init__(self):
        self._lock = threading.RLock()
        self.users = {}          # id -> user dict
        self.users_by_name = {}  # username -> id
        self.notes = {}          # id -> note dict
        self.audit_log = []      # list of audit entries
        self._user_seq = itertools.count(1)
        self._note_seq = itertools.count(1)
        self._audit_seq = itertools.count(1)

    # -- users -------------------------------------------------------------
    def create_user(self, username, password_hash, role="user"):
        with self._lock:
            if username in self.users_by_name:
                return None
            uid = next(self._user_seq)
            user = {
                "id": uid,
                "username": username,
                "password_hash": password_hash,
                "role": role,
                "created_at": utcnow().isoformat(),
            }
            self.users[uid] = user
            self.users_by_name[username] = uid
            return user

    def get_user(self, user_id):
        return self.users.get(user_id)

    def get_user_by_username(self, username):
        uid = self.users_by_name.get(username)
        return self.users.get(uid) if uid else None

    # -- notes -------------------------------------------------------------
    def create_note(self, owner_id, title, body, tags):
        with self._lock:
            nid = next(self._note_seq)
            note = {
                "id": nid,
                "owner_id": owner_id,
                "title": title,
                "body": body,
                "tags": tags,
                "created_at": utcnow().isoformat(),
                "updated_at": utcnow().isoformat(),
            }
            self.notes[nid] = note
            return note

    def get_note(self, note_id):
        return self.notes.get(note_id)

    def update_note(self, note_id, **fields):
        with self._lock:
            note = self.notes.get(note_id)
            if not note:
                return None
            note.update(fields)
            note["updated_at"] = utcnow().isoformat()
            return note

    def delete_note(self, note_id):
        with self._lock:
            return self.notes.pop(note_id, None)

    def list_notes(self, owner_id=None):
        notes = list(self.notes.values())
        if owner_id is not None:
            notes = [n for n in notes if n["owner_id"] == owner_id]
        return sorted(notes, key=lambda n: n["id"])

    # -- audit -------------------------------------------------------------
    def add_audit(self, entry):
        with self._lock:
            entry = dict(entry, id=next(self._audit_seq))
            self.audit_log.append(entry)
            return entry

    def list_audit(self):
        return list(self.audit_log)
