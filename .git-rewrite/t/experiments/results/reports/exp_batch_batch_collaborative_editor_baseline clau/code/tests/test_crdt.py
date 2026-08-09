"""CRDT convergence and conflict-resolution tests."""

from collab.crdt import DeleteOp, Document


def replicate(src: Document, dst: Document) -> None:
    for op_id in list(src._applied):
        pass  # not used; ops replayed explicitly in tests


def test_basic_insert_and_text():
    d = Document("A")
    d.local_insert_text(0, "hello")
    assert d.text == "hello"
    assert len(d) == 5


def test_insert_in_middle():
    d = Document("A")
    d.local_insert_text(0, "hd")
    d.local_insert_text(1, "ello worl")
    assert d.text == "hello world"


def test_delete():
    d = Document("A")
    d.local_insert_text(0, "hello")
    d.local_delete(1, 3)
    assert d.text == "ho"
    # tombstones retained for convergence/undo
    assert len(d.nodes) == 5


def test_two_replicas_converge_sequential():
    a, b = Document("A"), Document("B")
    ops = a.local_insert_text(0, "abc")
    for op in ops:
        b.apply(op)
    assert b.text == "abc"
    ops2 = b.local_insert_text(3, "def")
    for op in ops2:
        a.apply(op)
    assert a.text == b.text == "abcdef"


def test_concurrent_inserts_converge():
    a, b = Document("A"), Document("B")
    ops_a = a.local_insert_text(0, "hello")
    ops_b = b.local_insert_text(0, "world")
    for op in ops_b:
        a.apply(op)
    for op in ops_a:
        b.apply(op)
    assert a.text == b.text
    assert "hello" in a.text and "world" in a.text


def test_concurrent_runs_do_not_interleave():
    a, b = Document("A"), Document("B")
    ops_a = a.local_insert_text(0, "aaaa")
    ops_b = b.local_insert_text(0, "bbbb")
    for op in ops_b:
        a.apply(op)
    for op in ops_a:
        b.apply(op)
    assert a.text == b.text
    assert a.text in ("aaaabbbb", "bbbbaaaa")


def test_concurrent_insert_same_spot_deterministic_order():
    base = Document("S")
    base_ops = base.local_insert_text(0, "xy")

    a, b = Document("A"), Document("B")
    for op in base_ops:
        a.apply(op)
        b.apply(op)

    op_a = a.local_insert(1, "1")
    op_b = b.local_insert(1, "2")
    a.apply(op_b)
    b.apply(op_a)
    assert a.text == b.text
    assert sorted(a.text) == ["1", "2", "x", "y"]


def test_concurrent_delete_same_char_converges():
    a, b = Document("A"), Document("B")
    ops = a.local_insert_text(0, "abc")
    for op in ops:
        b.apply(op)
    del_a = a.local_delete(1)
    del_b = b.local_delete(1)
    for op in del_b:
        a.apply(op)
    for op in del_a:
        b.apply(op)
    assert a.text == b.text == "ac"


def test_out_of_order_delivery_is_buffered():
    a = Document("A")
    b = Document("B")
    ops = a.local_insert_text(0, "abc")  # each insert depends on the previous
    # deliver in reverse order
    for op in reversed(ops):
        b.apply(op)
    assert b.text == "abc"
    assert not b.pending


def test_delete_arriving_before_insert_is_buffered():
    a = Document("A")
    b = Document("B")
    ins = a.local_insert(0, "x")
    dels = a.local_delete(0)
    b.apply(dels[0])  # delete arrives first
    assert b.text == ""
    b.apply(ins)
    assert b.text == ""  # buffered delete applied after insert
    assert not b.pending


def test_duplicate_delivery_is_idempotent():
    a, b = Document("A"), Document("B")
    ops = a.local_insert_text(0, "hi")
    for op in ops + ops + ops:
        b.apply(op)
    assert b.text == "hi"


def test_three_replicas_converge():
    docs = [Document(s) for s in "ABC"]
    all_ops = []
    for i, d in enumerate(docs):
        all_ops.extend(d.local_insert_text(0, f"user{i} "))
    for d in docs:
        for op in all_ops:
            d.apply(op)
    assert docs[0].text == docs[1].text == docs[2].text
    for i in range(3):
        assert f"user{i} " in docs[0].text


def test_insert_after_concurrent_delete_of_origin():
    a, b = Document("A"), Document("B")
    ops = a.local_insert_text(0, "abc")
    for op in ops:
        b.apply(op)
    # A deletes 'b' while B inserts after 'b'
    del_ops = a.local_delete(1)
    ins_op = b.local_insert(2, "X")  # origin is 'b'
    for op in del_ops:
        b.apply(op)
    a.apply(ins_op)
    assert a.text == b.text == "aXc"
