"""Sync engine tests: realtime relay, offline editing, reconnect convergence."""

from collab.sync import Client, Server


def test_realtime_sync_two_clients():
    server = Server()
    a = Client("A", server)
    b = Client("B", server)
    a.insert(0, "hello")
    b.sync()
    assert b.text == "hello"
    b.insert(5, " world")
    a.sync()
    assert a.text == b.text == "hello world"


def test_offline_edit_then_reconnect():
    server = Server()
    a = Client("A", server)
    b = Client("B", server)
    a.insert(0, "base ")
    b.sync()

    b.disconnect()
    b.insert(5, "offline-edit")
    assert b.text == "base offline-edit"
    assert a.text == "base "  # not yet visible to A

    b.connect()
    a.sync()
    assert a.text == b.text == "base offline-edit"


def test_both_sides_edit_while_disconnected():
    server = Server()
    a = Client("A", server)
    b = Client("B", server)
    a.insert(0, "doc: ")
    b.sync()

    b.disconnect()
    a.insert(5, "from-a ")
    b.insert(5, "from-b ")

    b.connect()
    a.sync()
    b.sync()
    assert a.text == b.text
    assert "from-a " in a.text and "from-b " in a.text
    assert a.text.startswith("doc: ")


def test_offline_delete_conflicts_with_remote_insert():
    server = Server()
    a = Client("A", server)
    b = Client("B", server)
    a.insert(0, "abcdef")
    b.sync()

    b.disconnect()
    b.delete(0, 3)       # b removes "abc" offline
    a.insert(6, "xyz")   # a appends online

    b.connect()
    a.sync()
    assert a.text == b.text == "defxyz"


def test_reconnect_is_idempotent():
    server = Server()
    a = Client("A", server)
    a.insert(0, "hello")
    a.disconnect()
    a.connect()
    a.connect()
    a.sync()
    assert a.text == "hello"


def test_late_joiner_receives_full_history():
    server = Server()
    a = Client("A", server)
    a.insert(0, "hello")
    a.delete(0, 1)
    a.insert(0, "H")
    c = Client("C", server)  # joins after edits
    assert c.text == "Hello"


def test_three_clients_converge():
    server = Server()
    clients = [Client(s, server) for s in "ABC"]
    for i, c in enumerate(clients):
        c.insert(0, f"[{i}]")
    for c in clients:
        c.sync()
    texts = {c.text for c in clients}
    assert len(texts) == 1
    for i in range(3):
        assert f"[{i}]" in clients[0].text
