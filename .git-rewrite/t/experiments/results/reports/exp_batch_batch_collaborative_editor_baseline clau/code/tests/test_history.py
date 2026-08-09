"""Version history snapshot/restore tests."""

from collab.history import VersionHistory
from collab.sync import Client, Server


def pair():
    server = Server()
    return Client("A", server), Client("B", server)


def test_snapshot_captures_text():
    a, _ = pair()
    a.insert(0, "draft one")
    h = VersionHistory(a)
    v = h.snapshot("v1")
    a.insert(9, " plus more")
    assert h.get(v.id).text == "draft one"


def test_restore_previous_version():
    a, _ = pair()
    h = VersionHistory(a)
    a.insert(0, "hello world")
    v1 = h.snapshot("v1")
    a.delete(5, 6)
    a.insert(5, "!!!")
    assert a.text == "hello!!!"
    h.restore(v1.id)
    assert a.text == "hello world"


def test_restore_propagates_to_collaborators():
    a, b = pair()
    h = VersionHistory(a)
    a.insert(0, "original")
    v1 = h.snapshot("v1")
    b.sync()
    a.insert(8, " changed")
    h.restore(v1.id)
    b.sync()
    assert b.text == "original"


def test_restore_is_undoable():
    a, _ = pair()
    h = VersionHistory(a)
    a.insert(0, "abc")
    v1 = h.snapshot()
    a.insert(3, "def")
    h.restore(v1.id)
    assert a.text == "abc"
    a.undo()  # undo the restore's delete
    assert a.text == "abcdef"


def test_multiple_versions_listed_in_order():
    a, _ = pair()
    h = VersionHistory(a)
    a.insert(0, "1")
    h.snapshot("first")
    a.insert(1, "2")
    h.snapshot("second")
    assert [v.label for v in h.versions] == ["first", "second"]
    assert [v.text for v in h.versions] == ["1", "12"]


def test_restore_to_identical_text_is_noop():
    a, _ = pair()
    h = VersionHistory(a)
    a.insert(0, "same")
    v = h.snapshot()
    before = a.doc.clock
    h.restore(v.id)
    assert a.text == "same"
    assert a.doc.clock == before  # no ops generated
