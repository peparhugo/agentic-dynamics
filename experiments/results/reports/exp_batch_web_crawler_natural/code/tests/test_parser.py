from webcrawler.parser import parse_html

HTML = """
<html>
<head>
  <title>Hello World</title>
  <meta name="description" content="A test page">
  <link rel="canonical" href="/canonical-page">
  <meta name="robots" content="noindex, nofollow">
</head>
<body>
  <h1>Heading</h1>
  <p>Some visible text here.</p>
  <a href="/a">link a</a>
  <a href="/b" rel="nofollow">link b</a>
  <a href="javascript:void(0)">js</a>
</body>
</html>
"""


def test_parse_basic_fields():
    p = parse_html(HTML, url="http://x.com/dir/page")
    assert p.title == "Hello World"
    assert p.description == "A test page"
    assert p.canonical == "http://x.com/canonical-page"
    assert p.noindex is True
    assert p.nofollow is True


def test_parse_links_and_nofollow():
    p = parse_html(HTML, url="http://x.com/dir/page")
    assert len(p.links) == 3
    nofollow = [l.href for l in p.links if l.nofollow]
    assert "http://x.com/b" in nofollow
    assert "http://x.com/a" not in nofollow


def test_parse_absolute_links():
    p = parse_html(HTML, url="http://x.com/dir/page")
    absolute = p.absolute_links()
    assert "http://x.com/a" in absolute
    assert "http://x.com/b" in absolute


def test_followable_links_respect_nofollow():
    p = parse_html(HTML, url="http://x.com/dir/page")
    # page-level nofollow suppresses everything
    assert p.followable_links() == []

    html = '<html><body><a href="/keep">k</a><a href="/drop" rel="nofollow">d</a></body></html>'
    p2 = parse_html(html, url="http://x.com/")
    assert p2.followable_links() == ["http://x.com/keep"]


def test_parse_text_content():
    p = parse_html(HTML, url="http://x.com/")
    assert "Heading" in p.text
    assert "Some visible text here." in p.text


def test_parse_script_content_ignored():
    html = "<html><head><title>T</title></head><body><script>var x = 'SECRET';</script><p>Real</p></body></html>"
    p = parse_html(html, url="http://x.com/")
    assert "SECRET" not in p.text
    assert "Real" in p.text
