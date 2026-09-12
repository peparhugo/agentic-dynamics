"""Tests for the analytic route layer (steps 6–7): the GET routes are thin shells.

The routes render whatever the injected services return, with the services' status codes —
200 for a served projection, 404 for an unknown story — and never touch the filesystem
themselves. Read-only by construction: every registered method is GET.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _path in (_ROOT, _ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from flask import Flask  # noqa: E402

from apps.control_room.routes import analytics as route_analytics  # noqa: E402


class _FakeServices:
    def quality(self):
        return {"schema": "model-quality/v1", "models": [], "degraded": []}, 200

    def story_arc(self, name):
        if name == "s1":
            return {"schema": "story-arc/v1", "story": name, "sessions": []}, 200
        return {"error": "story not found", "story": name}, 404

    def run_value(self, *, run=None, arm=None):
        return {"schema": "run-value/v1", "run": run, "arm": arm, "rows": []}, 200

    def arm_comparison(self, spec=None):
        return {"schema": "arm-comparison/v1", "spec": spec, "state": "empty"}, 200

    def sla_queue(self, window_h=72):
        return {"schema": "sla-queue/v1", "window_h": window_h, "degraded": []}, 200

    def escalation(self, spec=None):
        return {"schema": "escalation-cascade/v1", "spec": spec, "armed": False}, 200

    def batch(self):
        return {"schema": "batch/v1", "measurable": False, "degraded": []}, 200

    def energy(self):
        return {"schema": "energy-epm/v1", "degraded": []}, 200


def _client(monkeypatch):
    """A test app wired to the fake services, with the module global restored on teardown."""
    monkeypatch.setattr(route_analytics, "_services", _FakeServices())
    app = Flask(__name__)
    route_analytics.register(app, route_analytics._services)
    return app.test_client()


def test_quality_route_serves_the_services_payload(monkeypatch):
    response = _client(monkeypatch).get("/api/quality")
    assert response.status_code == 200
    assert response.get_json()["schema"] == "model-quality/v1"


def test_story_arc_route_404s_an_unknown_story(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/api/stories/s1/arc").status_code == 200
    assert client.get("/api/stories/nope/arc").status_code == 404


def test_value_route_passes_exact_match_filters_through(monkeypatch):
    payload = _client(monkeypatch).get("/api/value?run=r1&arm=a").get_json()
    assert payload["run"] == "r1"
    assert payload["arm"] == "a"


def test_arms_compare_route_passes_the_spec_filter_through(monkeypatch):
    payload = _client(monkeypatch).get("/api/arms/compare?spec=x").get_json()
    assert payload["spec"] == "x"


def test_queue_sla_route_passes_and_clamps_the_window(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/api/queue/sla?window=24").get_json()["window_h"] == 24
    # invalid/absent window defaults; out-of-range clamps into the supported band
    assert client.get("/api/queue/sla").get_json()["window_h"] == 72
    assert client.get("/api/queue/sla?window=99999").get_json()["window_h"] == 720
    assert client.get("/api/queue/sla?window=nope").get_json()["window_h"] == 72


def test_escalations_route_passes_the_spec_filter_through(monkeypatch):
    payload = _client(monkeypatch).get("/api/escalations?spec=x").get_json()
    assert payload["spec"] == "x"


def test_batch_and_energy_routes_serve_their_payloads(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/api/batch").get_json()["schema"] == "batch/v1"
    assert client.get("/api/energy").get_json()["schema"] == "energy-epm/v1"


def test_analytics_routes_are_read_only_get(monkeypatch):
    monkeypatch.setattr(route_analytics, "_services", _FakeServices())
    app = Flask(__name__)
    route_analytics.register(app, route_analytics._services)
    methods = {
        rule.rule: rule.methods
        for rule in app.url_map.iter_rules()
        if rule.rule.startswith("/api/")
    }
    assert methods.keys() == {
        "/api/quality",
        "/api/stories/<name>/arc",
        "/api/value",
        "/api/arms/compare",
        "/api/queue/sla",
        "/api/escalations",
        "/api/batch",
        "/api/energy",
    }
    for rule, allowed in methods.items():
        assert allowed == {"GET", "HEAD", "OPTIONS"}, f"{rule} allows {allowed}"
