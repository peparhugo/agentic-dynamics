"""Unit C — native session binding + capsule semantics (``aio-session-binding/v1``).

The durable binding is the answer to "which task is this native session running, from which
explicit origin, under which acceptance" — written once, read by every later capsule request,
and never silently replaced. These tests exercise the read/write seams against a tmp artifact
dir + a fake stream (no Redis, no model calls, no subprocesses), and the capsule composer with
injected packet/budget states.
"""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest

from agentic_dynamics.knowledge import session_ingestion as si

ROOT = Path(__file__).resolve().parent.parent


class _FakeRedis:
    """In-memory stand-in for the knowledge stream (hget/hset/xadd surface)."""

    def __init__(self):
        self.hash: dict[str, str] = {}
        self.stream: dict[str, dict] = {}
        self._n = 0

    def hset(self, key, field, value):  # noqa: A003 - redis-shaped surface
        self.hash[field] = value

    def hget(self, key, field):
        return self.hash.get(field)

    def xadd(self, stream, payload):
        self._n += 1
        entry_id = f"1-{self._n}"
        self.stream[entry_id] = payload
        return entry_id


def _load_session_open(name: str = "session_open_under_test"):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "session_open.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _binding(**overrides) -> dict:
    binding = {
        "native_session_id": "ses_test_1",
        "resolved_agent": "aio-control",
        "initiating_message_id": "msg_1",
        "task_identity": "task-unit-c",
        "original_request": "Implement the native binding and capsule.",
        "predecessor": {"slug": "bound-predecessor", "knowledge_ids": []},
        "acceptance": None,
        "work_unit": "unit C",
    }
    binding.update(overrides)
    return binding


def _close(slug: str, *, date: str, artifact_dir: Path):
    redis = _FakeRedis()
    return si.close_session(
        {
            "session_date": date,
            "slug": slug,
            "waves_run": [f"{slug} ran"],
            "merged": [],
            "parked": [],
            "open_threads": [f"{slug} first thread", f"{slug} second thread"],
            "self_notes": f"notes for {slug}",
        },
        artifact_dir=artifact_dir,
        connect_fn=lambda: redis,
    )


class TestBindingStore:
    def test_binding_round_trips_and_survives_a_restart(self, tmp_path):
        result = si.write_binding(_binding(), artifact_dir=tmp_path, connect_fn=_FakeRedis)
        assert result.status == si.BINDING_STATUS_CREATED
        assert result.knowledge_id
        assert result.path.is_file()
        # The slot points at a content-addressed artifact; both halves are durable.
        assert (tmp_path / f"{result.knowledge_id}.json").is_file()

        # A restart is a fresh read against the same durable store — no process map needed.
        again = si.read_binding("ses_test_1", artifact_dir=tmp_path)
        assert again.status == si.BINDING_STATUS_FOUND
        assert again.knowledge_id == result.knowledge_id
        assert again.binding["original_request"] == "Implement the native binding and capsule."
        assert len(again.binding["original_request_sha256"]) == 64
        assert again.binding["resolved_agent"] == "aio-control"

    def test_an_existing_binding_is_never_replaced(self, tmp_path):
        first = si.write_binding(_binding(), artifact_dir=tmp_path, connect_fn=_FakeRedis)
        second = si.write_binding(
            _binding(original_request="A DIFFERENT REQUEST"),
            artifact_dir=tmp_path,
            connect_fn=_FakeRedis,
        )
        assert second.status == si.BINDING_STATUS_EXISTING
        assert second.knowledge_id == first.knowledge_id
        read = si.read_binding("ses_test_1", artifact_dir=tmp_path)
        assert read.binding["original_request"] == "Implement the native binding and capsule."

    def test_store_missing_differs_from_a_missing_binding(self, tmp_path):
        absent = tmp_path / "no-such-root"
        result = si.read_binding("ses_test_1", artifact_dir=absent)
        assert result.status == si.BINDING_STATUS_STORE_MISSING
        assert any("absent" in w for w in result.warnings)
        assert any("NOT first-session bootstrap" in w for w in result.warnings)

        present = tmp_path / "store"
        present.mkdir()
        result = si.read_binding("ses_test_1", artifact_dir=present)
        assert result.status == si.BINDING_STATUS_MISSING  # the store is there; no binding

    def test_a_corrupt_slot_is_named_and_never_overwritten(self, tmp_path):
        written = si.write_binding(_binding(), artifact_dir=tmp_path, connect_fn=_FakeRedis)
        written.path.write_text("{not json", encoding="utf-8")
        result = si.read_binding("ses_test_1", artifact_dir=tmp_path)
        assert result.status == si.BINDING_STATUS_CORRUPT
        with pytest.raises(ValueError):
            si.write_binding(_binding(), artifact_dir=tmp_path, connect_fn=_FakeRedis)

    def test_acceptance_interpretations_require_provenance(self, tmp_path):
        with pytest.raises(ValueError):
            si.write_binding(
                _binding(acceptance={"text": "tests green", "source": "interpretation"}),
                artifact_dir=tmp_path,
                connect_fn=_FakeRedis,
            )
        ok = si.write_binding(
            _binding(acceptance={
                "text": "tests green",
                "source": "interpretation",
                "provenance": "extracted by model X from message msg_1",
            }),
            artifact_dir=tmp_path,
            connect_fn=_FakeRedis,
        )
        assert ok.status == si.BINDING_STATUS_CREATED
        assert ok.binding["acceptance"]["provenance"].startswith("extracted by model X")


class TestCapsuleComposition:
    def _capsule(self, tmp_path, binding, **kwargs):
        module = _load_session_open()
        packet = kwargs.pop("packet", {"status": "observed", "payload": {
            "schema": "control-status/v1", "control_epoch": 42, "repo_head_sha": "abc",
            "active_runs": [], "awaiting_approvals": [], "safe_actions": [],
            "degraded": [], "projection_lag": {"registry": 0},
        }})
        budget = kwargs.pop("budget", {"verdict": "OK", "turns": 2, "context_tokens": 100})
        return module.compose_capsule(
            binding, artifact_dir=tmp_path, packet=packet, budget=budget, **kwargs
        )

    def test_capsule_ignores_an_unrelated_newer_close(self, tmp_path):
        _close("bound-predecessor", date="2026-09-10", artifact_dir=tmp_path)
        _close("unrelated-newer", date="2026-09-14", artifact_dir=tmp_path)
        # Control: the default "last close" read DOES resolve the unrelated newer one.
        latest = si.open_session(artifact_dir=tmp_path)
        assert latest.slug == "unrelated-newer"

        capsule = self._capsule(tmp_path, _binding())
        assert capsule["predecessor"]["close"]["slug"] == "bound-predecessor"
        assert "unrelated-newer" not in capsule["text"]

    def test_capsule_carries_selected_records_with_ids(self, tmp_path):
        close = _close("bound-predecessor", date="2026-09-10", artifact_dir=tmp_path)
        capsule = self._capsule(
            tmp_path,
            _binding(predecessor={
                "slug": "bound-predecessor",
                "knowledge_ids": [close.record.knowledge_id, "0" * 12],
            }),
            max_records=1,
        )
        records = capsule["predecessor"]["records"]
        assert len(records) == 1
        assert records[0]["knowledge_id"] == close.record.knowledge_id
        assert records[0]["status"] == "found"
        assert records[0]["source_type"] == "meta_session"
        # The id beyond the record bound is named, never silently dropped.
        assert capsule["predecessor"]["omitted"] == ["0" * 12]

    def test_capsule_bounds_are_explicit(self, tmp_path):
        long_request = "R" * 5000
        capsule = self._capsule(tmp_path, _binding(original_request=long_request))
        assert capsule["original_request"]["truncated"] is True
        assert capsule["original_request"]["omitted_chars"] == 5000 - len(capsule["original_request"]["text"])
        assert "[truncated:" in capsule["text"]

        tiny = self._capsule(tmp_path, _binding(), max_chars=200)
        assert tiny["bounds"]["truncated"] is True
        assert "[capsule truncated:" in tiny["text"]

    def test_capsule_packet_and_budget_states_are_explicit(self, tmp_path):
        capsule = self._capsule(
            tmp_path,
            _binding(),
            packet={"status": "unavailable", "reason": "timeout waiting for control_status.py"},
            budget={"verdict": "UNJUDGED", "reason": "no session identity"},
        )
        assert capsule["control_packet"]["status"] == "unavailable"
        assert "timeout" in capsule["control_packet"]["reason"]
        assert capsule["session_budget"]["verdict"] == "UNJUDGED"
        assert "control packet: UNAVAILABLE" in capsule["text"]
        # An unknown projection lag is surfaced as unknown, never as zero.
        observed = self._capsule(
            tmp_path,
            _binding(),
            packet={"status": "observed", "payload": {
                "schema": "control-status/v1", "control_epoch": 7, "repo_head_sha": "abc",
                "active_runs": [], "awaiting_approvals": [], "safe_actions": [],
                "degraded": ["failed_runs"],
                "projection_lag": {"registry": 0, "chroma": None},
            }},
        )
        assert observed["control_packet"]["unknowns"]["projection_lag_null"] == ["chroma"]
        assert observed["control_packet"]["degraded"] == ["failed_runs"]

    def test_next_action_precedence(self, tmp_path):
        _close("bound-predecessor", date="2026-09-10", artifact_dir=tmp_path)
        explicit = self._capsule(tmp_path, _binding(next_action="ship it"))
        assert explicit["next_action"] == {"text": "ship it", "source": "binding"}

        from_thread = self._capsule(tmp_path, _binding())
        assert from_thread["next_action"]["source"] == "predecessor-open-thread"
        assert "first thread" in from_thread["next_action"]["text"]

        orphan = self._capsule(tmp_path, _binding(predecessor={"slug": "no-such-close"}))
        assert orphan["next_action"]["source"] == "unavailable"
        assert orphan["predecessor"]["close"]["status"] == "not_found"


class TestCliModes:
    def test_cli_bind_and_capsule_round_trip(self, tmp_path, monkeypatch, capsys):
        module = _load_session_open("session_open_cli_test")
        monkeypatch.setattr(module, "read_control_packet",
                            lambda timeout=20: {"status": "observed", "payload": {
                                "schema": "control-status/v1", "control_epoch": 9,
                                "repo_head_sha": "abc", "active_runs": [],
                                "awaiting_approvals": [], "safe_actions": [], "degraded": [],
                                "projection_lag": {},
                            }})
        monkeypatch.setattr(module, "measure_budget",
                            lambda sid, timeout=20: {"verdict": "WARN", "turns": 80,
                                                     "context_tokens": 200000, "reason": ""})
        monkeypatch.setattr("sys.stdin", io.StringIO("The original request text."))

        assert module.main([
            "--bind", "--native-session-id", "ses_cli", "--agent", "aio-control",
            "--message-id", "m1", "--request-file", "-", "--task", "t-cli",
            "--artifact-dir", str(tmp_path), "--json",
        ]) == 0
        bound = json.loads(capsys.readouterr().out)
        assert bound["status"] == "created"

        assert module.main([
            "--capsule", "--native-session-id", "ses_cli",
            "--artifact-dir", str(tmp_path), "--json",
        ]) == 0
        capsule = json.loads(capsys.readouterr().out)
        assert capsule["capsule_status"] == "composed"
        assert "session budget: WARN" in capsule["capsule"]["text"]
        assert "The original request text." in capsule["capsule"]["text"]

    def test_cli_requires_a_native_session_id_for_binding_modes(self, capsys):
        module = _load_session_open("session_open_cli_usage_test")
        assert module.main(["--binding", "--json"]) == 2
        assert "required" in capsys.readouterr().err

    def test_cli_capsule_without_a_binding_composes_nothing(self, tmp_path, capsys):
        module = _load_session_open("session_open_cli_missing_test")
        (tmp_path / "empty").mkdir()
        assert module.main([
            "--capsule", "--native-session-id", "ses_none",
            "--artifact-dir", str(tmp_path / "empty"), "--json",
        ]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["capsule"] is None
        assert report["capsule_status"] == "missing"
