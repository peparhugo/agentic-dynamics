"""Version history: named snapshots + restore.

Restore is expressed as ordinary local edits (minimal prefix/suffix diff), so
it flows through the same CRDT/sync pipeline, is undoable, and propagates to
all collaborators.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Version:
    id: int
    label: str
    text: str
    timestamp: float


class VersionHistory:
    def __init__(self, client):
        self.client = client
        self.versions: List[Version] = []

    def snapshot(self, label: str = "") -> Version:
        v = Version(len(self.versions) + 1, label, self.client.text, time.time())
        self.versions.append(v)
        return v

    def get(self, version_id: int) -> Version:
        for v in self.versions:
            if v.id == version_id:
                return v
        raise KeyError(version_id)

    def restore(self, version_id: int) -> None:
        target = self.get(version_id).text
        current = self.client.text

        # minimal common prefix/suffix diff
        p = 0
        limit = min(len(current), len(target))
        while p < limit and current[p] == target[p]:
            p += 1
        s = 0
        while s < limit - p and current[len(current) - 1 - s] == target[len(target) - 1 - s]:
            s += 1

        delete_len = len(current) - p - s
        if delete_len:
            self.client.delete(p, delete_len)
        insertion = target[p:len(target) - s]
        if insertion:
            self.client.insert(p, insertion)
