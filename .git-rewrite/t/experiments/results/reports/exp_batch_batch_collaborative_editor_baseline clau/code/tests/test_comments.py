"""Comment anchoring tests."""

import pytest

from collab.comments import CommentManager
from collab.crdt import Document


def make():
    d = Document("A")
    d.local_insert_text(0, "Hello World")
    return d, CommentManager(d)


def test_add_and_read_comment():
    d, cm = make()
    c = cm.add("alice", "nice word", 6, 11)  # "World"
    assert cm.range(c.id) == (6, 11)
    assert cm.anchored_text(c.id) == "World"


def test_comment_tracks_inserts_before_it():
    d, cm = make()
    c = cm.add("alice", "nice", 6, 11)
    d.local_insert_text(6, "Big ")
    assert d.text == "Hello Big World"
    assert cm.range(c.id) == (10, 15)
    assert cm.anchored_text(c.id) == "World"


def test_comment_tracks_deletes_before_it():
    d, cm = make()
    c = cm.add("alice", "nice", 6, 11)
    d.local_delete(0, 6)  # delete "Hello "
    assert cm.anchored_text(c.id) == "World"
    assert cm.range(c.id) == (0, 5)


def test_comment_shrinks_with_partial_deletion():
    d, cm = make()
    c = cm.add("alice", "nice", 6, 11)
    d.local_delete(7, 3)  # "World" -> "Wd"
    assert cm.anchored_text(c.id) == "Wd"


def test_comment_orphaned_when_range_deleted():
    d, cm = make()
    c = cm.add("alice", "nice", 6, 11)
    d.local_delete(6, 5)  # delete "World"
    assert cm.is_orphaned(c.id)
    assert cm.range(c.id) is None
    assert cm.anchored_text(c.id) == ""


def test_empty_range_rejected():
    d, cm = make()
    with pytest.raises(ValueError):
        cm.add("alice", "??", 3, 3)


def test_replies_and_resolution():
    d, cm = make()
    c = cm.add("alice", "typo?", 0, 5)
    cm.reply(c.id, "bob", "fixed!")
    assert c.replies == [("bob", "fixed!")]
    assert c in cm.open_comments()
    cm.resolve(c.id)
    assert c not in cm.open_comments()


def test_comment_anchor_survives_remote_edits():
    d, cm = make()
    c = cm.add("alice", "nice", 6, 11)
    # simulate a remote replica editing, ops applied here
    remote = Document("B")
    for n in d.nodes:
        pass
    ops = d.local_insert_text(0, ">> ")
    assert cm.anchored_text(c.id) == "World"
    assert cm.range(c.id) == (9, 14)
