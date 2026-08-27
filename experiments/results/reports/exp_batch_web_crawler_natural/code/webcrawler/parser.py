"""HTML parsing and link extraction.

Uses only the standard library (``html.parser``) so the crawler has no
third-party dependency.  Extracts:

* the page ``title``, ``meta description`` and ``canonical`` URL,
* ``meta robots`` directives (``noindex`` / ``nofollow``) used for legal
  compliance and crawl steering,
* all ``<a href>`` links (with their ``rel=nofollow`` flag),
* the visible text content (for content hashing / dedup),
* ``last-modified`` style hints are handled by the fetcher instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import List, Optional
from urllib.parse import urljoin

# Tags whose text should contribute to the "content" used for dedup.
_TEXT_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th", "span", "a", "title"}


@dataclass
class Link:
    href: str
    nofollow: bool = False


@dataclass
class ParsedPage:
    url: str
    title: str = ""
    description: str = ""
    canonical: Optional[str] = None
    noindex: bool = False
    nofollow: bool = False
    links: List[Link] = field(default_factory=list)
    text: str = ""

    def absolute_links(self, base: Optional[str] = None) -> List[str]:
        base = base or self.url
        return [urljoin(base, link.href) for link in self.links]

    def followable_links(self, base: Optional[str] = None) -> List[str]:
        base = base or self.url
        return [
            urljoin(base, link.href)
            for link in self.links
            if not link.nofollow and not self.nofollow
        ]


class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts: List[str] = []
        self.description = ""
        self.canonical: Optional[str] = None
        self.noindex = False
        self.nofollow = False
        self.links: List[Link] = []
        self._text: List[str] = []
        self._in_title = False
        self._in_script_style = 0
        self._base_href: Optional[str] = None
        self._skip_stack: List[bool] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs = dict((k.lower(), v) for k, v in attrs)
        if tag in ("script", "style"):
            self._in_script_style += 1
            return
        if tag == "title":
            self._in_title = True
        if tag == "a":
            href = attrs.get("href")
            if href:
                rel = (attrs.get("rel") or "").lower().split()
                self.links.append(Link(href=href, nofollow="nofollow" in rel))
        if tag == "meta":
            name = (attrs.get("name") or "").lower()
            content = attrs.get("content") or ""
            if name == "description" and content and not self.description:
                self.description = content
            if name == "robots":
                lowered = content.lower()
                if "noindex" in lowered:
                    self.noindex = True
                if "nofollow" in lowered:
                    self.nofollow = True
        if tag == "link" and (attrs.get("rel") or "").lower() == "canonical":
            self.canonical = attrs.get("href")
        if tag == "base" and attrs.get("href"):
            self._base_href = attrs["href"]
        if tag in _TEXT_TAGS:
            self._text.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("script", "style"):
            self._in_script_style = max(0, self._in_script_style - 1)
            return
        if tag == "title":
            self._in_title = False
        if tag in _TEXT_TAGS:
            self._text.append("\n")

    def handle_data(self, data):
        if self._in_script_style:
            return
        if self._in_title:
            self.title_parts.append(data)
        self._text.append(data)

    @property
    def title(self) -> str:
        return "".join(self.title_parts).strip()

    @property
    def text(self) -> str:
        return " ".join("".join(self._text).split())


def parse_html(html: str, url: str = "") -> ParsedPage:
    parser = _Extractor()
    parser.feed(html)
    parser.close()
    base = parser._base_href or url or None
    links = parser.links
    if base:
        links = [Link(href=urljoin(base, l.href), nofollow=l.nofollow) for l in links]
    canonical = parser.canonical
    if canonical and base:
        canonical = urljoin(base, canonical)
    return ParsedPage(
        url=url,
        title=parser.title,
        description=parser.description,
        canonical=canonical,
        noindex=parser.noindex,
        nofollow=parser.nofollow,
        links=links,
        text=parser.text,
    )


__all__ = ["ParsedPage", "Link", "parse_html"]
