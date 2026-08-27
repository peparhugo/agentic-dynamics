"""URL normalization and canonicalization.

The web is full of syntactically distinct URLs that point at the same
resource (``example.com`` vs ``example.com:80``, ``/a`` vs ``/a/``,
``%7euser`` vs ``~user``, tracking query params, fragments, etc.).  If a
crawler treats these as distinct, it will crawl the same page millions of
times -- the classic cause of infinite loops at web scale.

Canonicalization collapses these equivalent spellings into a single key so
that the frontier's seen-set and the content deduper can recognize them.
"""

from __future__ import annotations

from urllib.parse import (
    parse_qsl,
    quote,
    unquote,
    urlencode,
    urljoin,
    urlsplit,
    urlunsplit,
)

DEFAULT_PORTS = {"http": 80, "https": 443}

# Common analytics/session query parameters that do not affect the page
# content.  Removing them dramatically reduces the number of unique URLs.
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "fbclid",
    "gclid",
    "gclsrc",
    "dclid",
    "msclkid",
    "ref",
    "referrer",
    "source",
    "session",
    "sessionid",
    "phpsessid",
    "jsessionid",
    "aspsessionid",
    "sid",
    "s",
    "tracking",
    "cmpid",
}

_SCHEMES = {"http", "https"}


def _lower_host(host: str) -> str:
    # IDN punycode hosts are already ASCII; lowercase everything.
    return host.lower()


def _split_host_port(netloc: str):
    """Split a netloc into (userinfo, host, port) without raising on
    malformed ports (``urlsplit().port`` raises ValueError on non-numeric
    ports, which we want to tolerate rather than crash on)."""
    userinfo = ""
    rest = netloc
    if "@" in rest:
        userinfo, rest = rest.rsplit("@", 1)
    host = rest
    port = None
    if rest.startswith("["):  # IPv6 literal
        end = rest.find("]")
        if end != -1:
            host = rest[: end + 1]
            tail = rest[end + 1 :]
            if tail.startswith(":"):
                port = tail[1:]
    elif ":" in rest:
        host, _, port = rest.rpartition(":")
    return userinfo, host, port


def _percent_encode(path: str, safe: str = "/:@") -> str:
    # Normalize percent-encoding: decode then re-encode with a canonical
    # character set.  This turns ``%7e`` -> ``~``, ``%2F`` -> ``%2F``, etc.
    return quote(unquote(path), safe=safe)


def _normalize_path(path: str) -> str:
    if path == "":
        path = "/"
    path = _percent_encode(path)
    # Collapse duplicate slashes in the path (but keep the scheme ``//``).
    import re

    path = re.sub(r"/{2,}", "/", path)
    # Remove trailing slash from the path component (except root).
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    # Resolve ``/./`` and ``/../`` segments.
    path = _collapse_dot_segments(path)
    return path


def _collapse_dot_segments(path: str) -> str:
    # RFC 3986 5.2.4 remove_dot_segments, simplified for absolute paths.
    segments = path.split("/")
    out = []
    for seg in segments:
        if seg == "." or seg == "":
            continue
        if seg == "..":
            if out and out[-1] != "..":
                out.pop()
            elif not out:
                continue
            else:
                out.append("..")
        else:
            out.append(seg)
    result = "/" + "/".join(out)
    return result if result != "" else "/"


def _normalize_query(query: str, sort_query: bool, strip_tracking: bool) -> str:
    if query == "":
        return ""
    pairs = parse_qsl(query, keep_blank_values=True)
    if strip_tracking:
        pairs = [(k, v) for k, v in pairs if k.lower() not in TRACKING_PARAMS]
    if sort_query:
        pairs = sorted(pairs, key=lambda kv: kv[0])
    return urlencode(pairs)


def normalize_url(
    url: str,
    sort_query: bool = True,
    strip_tracking: bool = True,
    strip_fragment: bool = True,
) -> str:
    """Return a canonical normalized form of ``url``.

    The result is deterministic so two URLs pointing at the same resource
    collapse to the same string.
    """
    if not url:
        return url
    parts = urlsplit(url.strip())

    scheme = parts.scheme.lower()
    if scheme not in _SCHEMES:
        return url  # unsupported scheme (mailto:, javascript:, ...) -> as-is

    userinfo, host, port = _split_host_port(parts.netloc)
    host = _lower_host(host)
    if port is not None and port.isdigit() and int(port) == DEFAULT_PORTS.get(scheme):
        port = None
    netloc = host
    if port is not None:
        netloc = f"{host}:{port}"
    if userinfo:
        netloc = f"{userinfo}@{netloc}"

    path = _normalize_path(parts.path)
    query = _normalize_query(parts.query, sort_query, strip_tracking)
    fragment = "" if strip_fragment else parts.fragment

    return urlunsplit((scheme, netloc, path, query, fragment))


def canonicalize_url(url: str, base: str | None = None) -> str:
    """Resolve ``url`` against ``base`` (if needed) and normalize it."""
    if base is not None:
        url = urljoin(base, url)
    return normalize_url(url)


def is_http_url(url: str) -> bool:
    scheme = urlsplit(url).scheme.lower()
    return scheme in _SCHEMES


def domain_of(url: str) -> str:
    """Return the registrable domain (host:port) for a URL."""
    parts = urlsplit(normalize_url(url))
    return parts.netloc.lower()


def hostname_of(url: str) -> str:
    return urlsplit(normalize_url(url)).hostname or ""


def same_host(url_a: str, url_b: str) -> bool:
    return hostname_of(url_a) == hostname_of(url_b)


def url_key(url: str) -> str:
    """A cheap hashable key for dedup (the normalized URL)."""
    return normalize_url(url)
