"""Rich-text formatting (toolbar model) tests."""

from collab.sync import Client, Server


def pair():
    server = Server()
    return Client("A", server), Client("B", server)


def test_bold_range():
    a, _ = pair()
    a.insert(0, "hello world")
    a.format(0, 5, "bold", True)
    spans = a.doc.spans()
    assert all(attrs == {"bold": True} for _c, attrs in spans[:5])
    assert all(attrs == {} for _c, attrs in spans[5:])


def test_overlapping_marks():
    a, _ = pair()
    a.insert(0, "abcdef")
    a.format(0, 4, "bold", True)
    a.format(2, 6, "italic", True)
    spans = a.doc.spans()
    assert spans[2][1] == {"bold": True, "italic": True}
    assert spans[0][1] == {"bold": True}
    assert spans[5][1] == {"italic": True}


def test_toolbar_state_for_selection():
    a, _ = pair()
    a.insert(0, "abcdef")
    a.format(0, 6, "bold", True)
    a.format(0, 3, "italic", True)
    # whole selection bold, only partially italic
    assert a.doc.marks_in_range(0, 6) == {"bold": True}
    assert a.doc.marks_in_range(0, 3) == {"bold": True, "italic": True}


def test_unbold():
    a, _ = pair()
    a.insert(0, "text")
    a.format(0, 4, "bold", True)
    a.format(0, 4, "bold", False)
    assert a.doc.marks_in_range(0, 4) == {}


def test_format_syncs_to_collaborator():
    a, b = pair()
    a.insert(0, "shared")
    b.sync()
    a.format(0, 6, "bold", True)
    b.sync()
    assert b.doc.marks_in_range(0, 6) == {"bold": True}


def test_concurrent_format_conflict_converges_lww():
    a, b = pair()
    a.insert(0, "word")
    b.sync()

    b.disconnect()
    a.format(0, 4, "bold", True)
    b.format(0, 4, "bold", False)
    b.connect()
    a.sync()
    b.sync()
    assert a.doc.spans() == b.doc.spans()


def test_formatting_survives_concurrent_insert():
    a, b = pair()
    a.insert(0, "bold")
    b.sync()
    b.disconnect()
    a.format(0, 4, "bold", True)
    b.insert(2, "XX")  # b splits the word offline
    b.connect()
    a.sync()
    b.sync()
    assert a.text == b.text == "boXXld"
    spans = dict()
    for ch, attrs in a.doc.spans():
        spans.setdefault(ch, attrs)
    # original chars keep bold; inserted chars are plain
    assert a.doc.spans() == b.doc.spans()
    marks = [attrs.get("bold", False) for _c, attrs in a.doc.spans()]
    assert marks == [True, True, False, False, True, True]


def test_link_mark_with_value():
    a, _ = pair()
    a.insert(0, "click here")
    a.format(6, 10, "link", "https://example.com")
    assert a.doc.marks_in_range(6, 10) == {"link": "https://example.com"}
