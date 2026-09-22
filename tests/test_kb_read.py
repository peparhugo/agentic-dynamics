"""Guard rails for ``scripts/kb_read.py`` — the reader verb must degrade, never crash.

``kb-read-degradation-crash`` (minted 2026-09-21): with no services the ranked path returns
``None`` and the deterministic fallback read ``registry_index.jsonl`` unguarded, raising
``FileNotFoundError`` when the durable registry was absent. A reader could not tell "registry
absent" from "no matches". The verb now (1) returns zero hits for an absent registry and (2)
reports the explicit ``unavailable`` mode. This module pins both — plus a positive control that
proves the scan still finds real rows, so stubbing ``_contains`` to return ``[]`` forever would
fail the suite instead of quietly passing.
"""

from __future__ import annotations

import argparse
import json

import pytest

from scripts import kb_read

pytestmark = pytest.mark.fast


def _args(**overrides) -> argparse.Namespace:
    """The minimal namespace ``_contains`` reads (query/type/lifecycle/limit)."""
    base = {"query": "needle", "type": "", "lifecycle": "current", "limit": 8, "contains": True}
    base.update(overrides)
    return argparse.Namespace(**base)


def test_contains_returns_empty_when_registry_absent(tmp_path, monkeypatch):
    """An absent registry is a degraded read, not an exception (the reproduced crash)."""
    monkeypatch.setattr(kb_read, "REGISTRY", tmp_path / "missing_registry.jsonl")
    assert kb_read._contains(_args()) == []


def test_contains_finds_a_row_against_a_tmp_registry(tmp_path, monkeypatch):
    """Positive control — the scan is non-vacuous: it finds a real matching row."""
    kb = tmp_path / "kb"
    kb.mkdir()
    kid = "k1"
    (kb / f"{kid}.json").write_text(
        json.dumps(
            {
                "text": "a cache hit rate measurement",
                "source_type": "finding",
                "authority": "MEASURED",
                "evidence_class": "[M]",
                "logical_locator": "loc",
            }
        ),
        encoding="utf-8",
    )
    registry = tmp_path / "registry_index.jsonl"
    registry.write_text(
        json.dumps({"knowledge_id": kid, "source_type": "finding", "lifecycle_state": "current"})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(kb_read, "KB_DIR", kb)
    monkeypatch.setattr(kb_read, "REGISTRY", registry)

    hits = kb_read._contains(_args(query="cache hit"))
    assert len(hits) == 1  # a stubbed `return []` would fail here
    assert hits[0]["id"] == kid
    assert hits[0]["mode"] == "contains"


def test_main_reports_unavailable_when_the_registry_is_absent(tmp_path, monkeypatch, capsys):
    """Both paths unavailable => an explicit ``unavailable`` mode, no traceback, exit 0."""
    monkeypatch.setattr(kb_read, "REGISTRY", tmp_path / "missing_registry.jsonl")
    monkeypatch.setattr(kb_read, "KB_DIR", tmp_path / "kb")
    monkeypatch.setattr("sys.argv", ["kb_read.py", "--query", "needle", "--contains"])

    assert kb_read.main() == 0
    out = capsys.readouterr().out
    assert "mode=unavailable" in out
    assert "UNAVAILABLE" in out  # the human line names the degradation
    assert "Traceback" not in out
