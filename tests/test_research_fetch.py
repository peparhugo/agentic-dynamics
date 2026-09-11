"""Tests for the research acquisition/provenance tool (research_fetch.py)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "research_fetch", _REPO / "scripts" / "research_fetch.py"
)
assert _SPEC is not None and _SPEC.loader is not None
mod = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = mod
_SPEC.loader.exec_module(mod)


HTML = b"""<html><head><title>Sleek Dashboards</title>
<script>var secret = 1;</script></head>
<body><h1>Control Rooms</h1><p>Density and hierarchy.</p>
<style>.x{}</style></body></html>"""


def test_extract_text_skips_script_and_style():
    title, text = mod._extract_text(HTML, "text/html; charset=utf-8")
    assert title == "Sleek Dashboards"
    assert "Control Rooms" in text
    assert "Density and hierarchy." in text
    assert "var secret" not in text


def test_store_source_dedups_by_content_hash(tmp_path):
    record = {
        "uri": "https://example.com/a",
        "final_url": "https://example.com/a",
        "status": 200,
        "content_type": "text/html",
        "sha256": "a" * 64,
        "title": "A",
        "text": "hello",
        "bytes": 5,
    }
    path, stored = mod.store_source(record, tmp_path)
    assert stored is True and path.exists()
    same_path, stored_again = mod.store_source(record, tmp_path)
    assert stored_again is False and same_path == path
    lines = (tmp_path / "sources.jsonl").read_text().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["sha256"] == "a" * 64
    payload = json.loads(path.read_text())
    assert payload["fetched_at"]


def test_fetch_source_reads_through_a_fake_response(monkeypatch):
    class _Response:
        status = 200
        headers = {"Content-Type": "text/html"}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return HTML

        def geturl(self):
            return "https://example.com/final"

    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda request, timeout: _Response())
    record = mod.fetch_source("https://example.com/start")
    assert record["final_url"] == "https://example.com/final"
    assert record["title"] == "Sleek Dashboards"
    assert record["bytes"] == len(HTML)
    assert len(record["sha256"]) == 64
