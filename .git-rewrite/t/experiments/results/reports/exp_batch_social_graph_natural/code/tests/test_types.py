from __future__ import annotations

import pytest
from social_graph.types import NodeID, Edge, User


class TestUser:
    def test_creation(self) -> None:
        u = User(user_id=1, name="Alice")
        assert u.user_id == 1
        assert u.name == "Alice"
        assert u.metadata == {}

    def test_metadata(self) -> None:
        u = User(user_id=2, name="Bob", metadata={"age": 30})
        assert u.metadata == {"age": 30}

    def test_slots(self) -> None:
        u = User(user_id=3)
        with pytest.raises(AttributeError):
            u.new_attr = 5  # type: ignore


class TestNodeID:
    def test_type(self) -> None:
        nid: NodeID = 42
        assert isinstance(nid, int)


class TestEdge:
    def test_type(self) -> None:
        edge: Edge = (1, 2)
        assert isinstance(edge, tuple)
        assert edge[0] == 1
        assert edge[1] == 2
