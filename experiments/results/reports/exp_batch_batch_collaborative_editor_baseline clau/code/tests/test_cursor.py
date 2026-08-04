"""Multi-user cursor / selection presence tests."""

from collab.crdt import Document
from collab.cursor import CursorManager


def make_doc(text="hello world"):
    d = Document("A")
    d.local_insert_text(0, text)
    return d


def test_cursor_roundtrip():
    d = make_doc()
    cm = CursorManager(d)
    cm.set_cursor("alice", 5)
    assert cm.get_index("alice") == 5


def test_cursor_at_start():
    d = make_doc()
    cm = CursorManager(d)
    cm.set_cursor("alice", 0)
    assert cm.get_index("alice") == 0


def test_cursor_shifts_on_insert_before():
    d = make_doc("hello")
    cm = CursorManager(d)
    cm.set_cursor("alice", 3)
    d.local_insert_text(0, ">> ")
    assert cm.get_index("alice") == 6


def test_cursor_stable_on_insert_after():
    d = make_doc("hello")
    cm = CursorManager(d)
    cm.set_cursor("alice", 3)
    d.local_insert_text(5, "!!!")
    assert cm.get_index("alice") == 3


def test_cursor_shifts_on_delete_before():
    d = make_doc("hello")
    cm = CursorManager(d)
    cm.set_cursor("alice", 4)
    d.local_delete(0, 2)
    assert cm.get_index("alice") == 2


def test_cursor_survives_deletion_of_anchor_char():
    d = make_doc("hello")
    cm = CursorManager(d)
    cm.set_cursor("alice", 3)  # anchored to 2nd 'l'
    d.local_delete(2)  # delete that 'l'
    assert cm.get_index("alice") == 2
    assert d.text == "helo"


def test_remote_presence_broadcast():
    a = Document("A")
    ops = a.local_insert_text(0, "shared text")
    b = Document("B")
    for op in ops:
        b.apply(op)

    cm_a = CursorManager(a)
    cm_b = CursorManager(b)
    anchors = cm_a.set_cursor("alice", 6)
    cm_b.receive("alice", anchors)  # presence message over the wire
    assert cm_b.get_index("alice") == 6

    # bob edits before alice's cursor; her remote cursor shifts on his screen
    b.local_insert_text(0, "** ")
    assert cm_b.get_index("alice") == 9


def test_selection_range():
    d = make_doc("hello world")
    cm = CursorManager(d)
    cm.set_selection("alice", 6, 11)
    assert cm.get_selection("alice") == (6, 11)
    d.local_insert_text(0, "X")
    assert cm.get_selection("alice") == (7, 12)


def test_all_positions_and_remove():
    d = make_doc()
    cm = CursorManager(d)
    cm.set_cursor("alice", 1)
    cm.set_cursor("bob", 4)
    assert cm.all_positions() == {"alice": (1, 1), "bob": (4, 4)}
    cm.remove("bob")
    assert "bob" not in cm.all_positions()
