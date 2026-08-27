"""Core data models for the social network graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class User:
    """A user (node) in the social graph.

    Attributes:
        id: Globally unique, immutable user identifier (e.g. a 64-bit snowflake id).
        name: Display name (denormalized onto the node for fast reads).
        metadata: Optional opaque attributes (email, employer, location, ...).
            Kept as a flat dict so it can be indexed / projected independently.
    """

    id: str
    name: str
    metadata: Dict[str, Any] = field(default_factory=dict, compare=False)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, User):
            return self.id == other.id
        return NotImplemented


@dataclass(frozen=True)
class Connection:
    """A directed/undirected edge between two users.

    The edge is stored twice (once per direction) inside the adjacency index
    so that neighbour lookups are O(1) and locality is preserved. `weight`
    carries an affinity score used for suggestions and community detection.
    """

    src: str
    dst: str
    weight: float = 1.0
    created_at: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict, compare=False)


@dataclass
class FriendSuggestion:
    """A candidate friend produced by a friend-of-friend query."""

    user_id: str
    mutual_friends: int
    score: float = 0.0

    def __lt__(self, other: "FriendSuggestion") -> bool:
        return (self.mutual_friends, self.score) < (
            other.mutual_friends,
            other.score,
        )


@dataclass(frozen=True)
class PathResult:
    """Result of a path-finding query between two users."""

    path: Optional[list]
    distance: int

    @property
    def connected(self) -> bool:
        return self.path is not None
