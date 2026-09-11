#!/usr/bin/env python3
"""Deterministic open-web acquisition with provenance — the research layer's fetch seam.

Every research source enters the corpus through this tool, so provenance is not a hope: each
source becomes one immutable record carrying ``uri``, the redirect-resolved ``final_url``,
``fetched_at`` (UTC), the raw-content ``sha256``, ``content_type``, the page ``title``, and the
extracted text. A content hash already in the corpus is a no-op (dedup); the append-only
catalog (``sources.jsonl``) records one line per stored source.

Cells reach the open web through the fleet's HTTP(S)_PROXY env (the egress policy point); the
tool itself is stdlib-only.

    python3 scripts/research_fetch.py https://example.com https://web.dev/…
    python3 scripts/research_fetch.py --from-file seeds.txt
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

try:
    import _bootstrap  # noqa: E402  # direct run: scripts/ is sys.path[0]
except ImportError:  # imported as scripts.<name> — repo root is on sys.path
    from scripts import _bootstrap  # noqa: E402,F401

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = REPO_ROOT / "experiments" / "results" / "research"
USER_AGENT = "ai-finops-research/1.0 (+research corpus acquisition)"


class _TextExtractor(HTMLParser):
    """Minimal HTML -> text: skips script/style/noscript, captures the title, joins block text."""

    _SKIP = {"script", "style", "noscript", "svg", "template"}
    _BLOCK = {
        "p", "div", "section", "article", "header", "footer", "li", "tr", "br", "h1", "h2",
        "h3", "h4", "h5", "h6", "pre", "blockquote", "figcaption",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._in_title = False
        self.title = ""
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data.strip()
        else:
            stripped = data.strip()
            if stripped:
                self.parts.append(stripped + " ")

    def text(self) -> str:
        raw = "".join(self.parts)
        lines = [" ".join(line.split()) for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


def _extract_text(body: bytes, content_type: str) -> tuple[str, str]:
    """Return ``(title, text)`` for a fetched body (HTML is parsed; other types pass through)."""
    if "html" in content_type.lower() or b"<html" in body[:2048].lower():
        parser = _TextExtractor()
        parser.feed(body.decode("utf-8", errors="replace"))
        return parser.title.strip(), parser.text()
    return "", body.decode("utf-8", errors="replace")


def fetch_source(url: str, *, timeout: int = 45) -> dict:
    """Fetch one URL and return its record fields (no filesystem writes)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 — research fetch
        body = response.read()
        content_type = response.headers.get("Content-Type", "")
        final_url = response.geturl()
        status = getattr(response, "status", 200) or 200
    title, text = _extract_text(body, content_type)
    return {
        "uri": url,
        "final_url": final_url,
        "status": status,
        "content_type": content_type,
        "sha256": hashlib.sha256(body).hexdigest(),
        "title": title,
        "text": text,
        "bytes": len(body),
    }


def _existing_hashes(source_dir: Path) -> set[str]:
    hashes: set[str] = set()
    for record in source_dir.glob("*.json"):
        try:
            hashes.add(json.loads(record.read_text())["sha256"])
        except (KeyError, ValueError):
            continue
    return hashes


def _display_path(path: Path) -> str:
    """Repo-relative when possible (records are readable either way)."""
    try:
        return _display_path(path)
    except ValueError:
        return str(path)


def store_source(record: dict, out_dir: Path) -> tuple[Path, bool]:
    """Write one source record (idempotent by content hash); append the catalog line.

    Returns ``(path, stored)`` — ``stored`` is False when the same content already exists.
    """
    source_dir = out_dir / "sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    path = source_dir / f"{record['sha256'][:16]}.json"
    stored = not path.exists()
    if stored:
        payload = {**record, "fetched_at": datetime.now(timezone.utc).isoformat()}
        path.write_text(json.dumps(payload, indent=2))
        with (out_dir / "sources.jsonl").open("a") as catalog:
            catalog.write(
                json.dumps(
                    {
                        "uri": record["uri"],
                        "final_url": record["final_url"],
                        "sha256": record["sha256"],
                        "title": record["title"],
                        "fetched_at": payload["fetched_at"],
                        "path": _display_path(path),
                    }
                )
                + "\n"
            )
    return path, stored


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("urls", nargs="*")
    parser.add_argument("--from-file", default="", help="newline-separated URL list")
    parser.add_argument("--out-dir", default=str(DEFAULT_DIR))
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--dry-run", action="store_true", help="fetch and report; do not store")
    args = parser.parse_args(argv)

    urls = list(args.urls)
    if args.from_file:
        urls += [line.strip() for line in Path(args.from_file).read_text().splitlines() if line.strip()]
    if not urls:
        print("research_fetch: no urls", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir)
    failures = 0
    for url in urls:
        try:
            record = fetch_source(url, timeout=args.timeout)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            failures += 1
            print(json.dumps({"uri": url, "error": repr(exc)[:200]}))
            continue
        if args.dry_run:
            print(json.dumps({k: record[k] for k in ("uri", "status", "title", "bytes", "sha256")}))
            continue
        path, stored = store_source(record, out_dir)
        print(
            json.dumps(
                {
                    "uri": url,
                    "stored": stored,
                    "path": _display_path(path),
                    "title": record["title"][:80],
                    "bytes": record["bytes"],
                }
            )
        )
    return 1 if failures == len(urls) else 0


if __name__ == "__main__":
    raise SystemExit(main())
