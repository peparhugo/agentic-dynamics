"""Undo/redo tests, including cross-collaborator semantics."""

from collab.sync import Client, Server


def pair():
    server = Server()
    return Client("A", server), Client("B", server)


def test_undo_insert():
    a, _ = pair()
    a.insert(0, "hello")
    assert a.undo()
    assert a.text == ""


def test_undo_then_redo_insert():
    a, _ = pair()
    a.insert(0, "hello")
    a.undo()
    assert a.redo()
    assert a.text == "hello"


def test_undo_delete_restores_text():
    a, _ = pair()
    a.insert(0, "hello")
    a.delete(1, 3)
    assert a.text == "ho"
    a.undo()
    assert a.text == "hello"


def test_undo_only_reverts_own_ops():
    a, b = pair()
    a.insert(0, "Hello ")
    b.sync()
    b.insert(6, "World")
    a.sync()
    assert a.text == "Hello World"

    a.undo()  # reverts A's "Hello ", not B's "World"
    b.sync()
    assert a.text == b.text == "World"


def test_redo_after_cross_collaborator_undo():
    a, b = pair()
    a.insert(0, "Hello ")
    b.sync()
    b.insert(6, "World")
    a.sync()
    a.undo()
    a.redo()
    b.sync()
    assert a.text == b.text == "Hello World"


def test_undo_works_after_remote_edits_shift_positions():
    a, b = pair()
    a.insert(0, "middle")
    b.sync()
    b.insert(0, "start ")  # shifts A's text right
    a.sync()
    assert a.text == "start middle"
    a.undo()  # must delete "middle", not whatever now sits at offset 0
    b.sync()
    assert a.text == b.text == "start "


def test_new_edit_clears_redo_stack():
    a, _ = pair()
    a.insert(0, "one")
    a.undo()
    a.insert(0, "two")
    assert not a.redo()
    assert a.text == "two"


def test_undo_stack_empty_returns_false():
    a, _ = pair()
    assert not a.undo()
    assert not a.redo()


def test_multi_step_undo_redo():
    a, _ = pair()
    a.insert(0, "one")
    a.insert(3, " two")
    a.insert(7, " three")
    a.undo()
    assert a.text == "one two"
    a.undo()
    assert a.text == "one"
    a.redo()
    a.redo()
    assert a.text == "one two three"


def test_undo_format():
    a, _ = pair()
    a.insert(0, "bold")
    a.format(0, 4, "bold", True)
    assert a.doc.marks_in_range(0, 4) == {"bold": True}
    a.undo()
    assert a.doc.marks_in_range(0, 4) == {}
    a.redo()
    assert a.doc.marks_in_range(0, 4) == {"bold": True}


def test_undo_propagates_to_collaborators():
    a, b = pair()
    a.insert(0, "temp")
    b.sync()
    assert b.text == "temp"
    a.undo()
    b.sync()
    assert b.text == ""
