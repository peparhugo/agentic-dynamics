from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple, Optional

NodeID = int
Edge = Tuple[NodeID, NodeID]


@dataclass(slots=True)
class User:
    user_id: NodeID
    name: str = ""
    metadata: dict = field(default_factory=dict)


_NON_EXISTENT: object = object()
