"""Tests for the routing board after the step-6 retirement (one-fact-one-writer).

``GET /api/routing`` used to read ``experiments/results/_results_summary.json`` — the corpus
the repo retired (``data_integrity_findings`` rule 4; every lab still reading it is
quarantined). It now maps the canonical finding rows (the one input door) onto
``compute_routing``'s entry shape; an unreadable corpus is a NAMED state, never stale numbers
from the retired summary. The last test is the source guard: the retired path may not return.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from flask import Flask  # noqa: E402

from apps.control_room import server as _server  # noqa: E402,F401  # composition root first
from apps.control_room.routes import telemetry as route_telemetry  # noqa: E402


class _Services:
    """The routing route reads no services at request time — register-time storage only."""


def _tables():
    findings = [
        {"model": "m/one", "_experiment": "task_manager", "correctness": 0.9, "cost_usd": 0.10},
        {"model": "m/one", "_experiment": "task_manager", "correctness": 0.8, "cost_usd": 0.12},
        {"model": "m/two", "_experiment": "task_manager", "correctness": 0.95, "cost_usd": 0.50},
    ]
    return SimpleNamespace(
        findings=findings,
        input_dataset_id="canonical_registry/finding",
        identity=SimpleNamespace(registry_version="test/1"),
    )


def _client(monkeypatch) -> Flask:
    """A test app wired to the fake services.

    The route module stores ``services`` in a module global; ``monkeypatch.setattr`` snapshots
    the real context first, so registering the fake app cannot leak into the shared
    ``server.app`` (the pollution that makes later admin tests flaky).
    """
    monkeypatch.setattr(route_telemetry, "_services", _Services())
    app = Flask(__name__)
    route_telemetry.register(app, route_telemetry._services)
    return app.test_client()


def test_api_routing_reads_the_canonical_corpus(monkeypatch):
    calls = []
    monkeypatch.setattr(
        route_telemetry,
        "load_canonical_tables",
        lambda *tables: calls.append(tables) or _tables(),
    )
    response = _client(monkeypatch).get("/api/routing")
    assert response.status_code == 200
    payload = response.get_json()
    assert calls == [("finding",)]
    assert payload["_meta"]["source"] == "canonical_corpus"
    assert payload["_meta"]["registry_version"] == "test/1"
    assert payload["_meta"]["tasks_analyzed"] == 1
    assert payload["per_task"][0]["task"] == "task_manager"


def test_api_routing_unreadable_corpus_is_named_not_stale(monkeypatch):
    def _boom(*tables):
        raise RuntimeError("no manifest")

    monkeypatch.setattr(route_telemetry, "load_canonical_tables", _boom)
    payload = _client(monkeypatch).get("/api/routing").get_json()
    assert payload["_meta"]["state"] == "unavailable"
    assert "no manifest" in payload["_meta"]["reason"]
    assert payload["per_task"] == []


def test_api_routing_no_longer_reads_the_retired_summary():
    """No non-docstring string in the module names the retired summary (AST, not grep).

    The module is allowed to *explain* the retirement in prose; it may not carry the path.
    """
    source = Path(route_telemetry.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docstrings.add(id(body[0].value))
    offenders = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
        and "_results_summary" in node.value
    ]
    assert not offenders, f"the retired summary path survives in code: {offenders}"
