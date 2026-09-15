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


class TestReadControlPacket:
    def test_an_exit_three_error_envelope_is_not_a_packet(self):
        """The CLI's exit-3 envelope REUSES the control-status/v1 schema id. Treating it as an
        observed packet would render "no database" as epoch None / active 0 — the empty-vs-
        missing conflation the contract forbids. It must be the explicit unavailable state."""
        module = _load_session_open("session_open_packet_test")
        envelope = {
            "schema": "control-status/v1",
            "error": "control_db_unavailable",
            "detail": "control_db: no control database at /tmp/x — a reader never creates one",
            "control_db": "",
        }
        module._run_json_command = lambda cmd, timeout: {
            "status": "observed", "payload": envelope, "exit_code": 3,
        }
        result = module.read_control_packet()
        assert result["status"] == "no_control_database"
        assert "no control database" in result["reason"]

    def test_a_real_packet_passes_through(self):
        module = _load_session_open("session_open_packet_ok_test")
        packet = {"schema": "control-status/v1", "control_epoch": 771, "active_runs": []}
        module._run_json_command = lambda cmd, timeout: {
            "status": "observed", "payload": packet, "exit_code": 0,
        }
        result = module.read_control_packet()
        assert result["status"] == "observed" and result["payload"] is packet


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
        assert capsule["original_request"]["omitted_chars"] > 0
        assert "[... " in capsule["original_request"]["text"]  # the middle-cut marker
        assert "[truncated:" in capsule["text"]

        tiny = self._capsule(tmp_path, _binding(original_request="R" * 4000), max_chars=650)
        assert tiny["bounds"]["truncated"] is True
        assert "capsule head truncated" in tiny["text"]

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

    def test_capsule_reports_the_capacity_derived_budget(self, tmp_path):
        """The v2 budget report rides into the capsule whole: resolved model, effective/hard
        limits, response headroom, remaining tokens, and the measurement provenance — and the
        rendered tail names the model and the effective limit, not only a verdict."""
        budget = {
            "verdict": "OK", "turns": 38, "context_tokens": 189_594,
            "usage_incomplete": True, "reason": "usage incomplete — last completed sample used",
            "model": {"provider_id": "deepseek", "model_id": "deepseek-v4-flash",
                      "variant": "max", "source": "session.model"},
            "capacity": {"effective_limit": 968_000, "hard_limit": 1_000_000,
                         "context_limit": 1_000_000, "input_limit": None,
                         "output_limit": 384_000, "response_headroom_tokens": 32_000,
                         "compaction_reserved_tokens": 15_000, "warn_fraction": 0.8,
                         "compaction_enabled": True},
            "remaining_tokens": 778_406,
            "provenance": {"formula": "opencode@1.18.15:SessionCompaction.isOverflow"},
        }
        capsule = self._capsule(tmp_path, _binding(), budget=budget)
        section = capsule["session_budget"]
        assert section["model"]["model_id"] == "deepseek-v4-flash"
        assert section["capacity"]["effective_limit"] == 968_000
        assert section["capacity"]["response_headroom_tokens"] == 32_000
        assert section["remaining_tokens"] == 778_406
        assert "opencode@1.18.15" in section["provenance"]["formula"]
        text = capsule["text"]
        assert "session budget: OK — deepseek/deepseek-v4-flash" in text
        assert "968000" in text and "headroom 32000" in text

        at_boundary = dict(budget, verdict="COMPACT", context_tokens=970_000)
        rendered = self._capsule(tmp_path, _binding(), budget=at_boundary)["text"]
        assert "session budget: COMPACT" in rendered

        # The post-compaction state renders explicitly: the stale pre-compaction reading is
        # labeled, never presented as the current context.
        compacted = dict(budget, post_compaction=True, remaining_tokens=None)
        capsule_after = self._capsule(tmp_path, _binding(), budget=compacted)
        assert capsule_after["session_budget"]["post_compaction"] is True
        assert "post-compaction (pre-compaction reading 189594" in capsule_after["text"]

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


class TestStoreHardening:
    def test_a_rejected_update_cannot_create_the_store(self, tmp_path):
        """The reviewer repair: the lock setup must not mkdir before the store check — a
        rejected update left `aio-bindings/` behind, letting a later bind silently succeed."""
        absent = tmp_path / "wrong-worktree" / "kb"
        with pytest.raises(ValueError):
            si.update_binding_context(
                "ses_x", context={"work_unit": "x"}, expected_version=1, artifact_dir=absent
            )
        assert not absent.exists(), "the rejected update created store directories"
        result = si.write_binding(
            _binding(native_session_id="ses_x"), artifact_dir=absent, publish=False
        )
        assert result.status == si.BINDING_STATUS_STORE_MISSING

    def test_write_requires_an_existing_store(self, tmp_path):
        """The reviewer repair: a native bind must NEVER create the durable root implicitly."""
        absent = tmp_path / "wrong-worktree" / "kb"
        result = si.write_binding(_binding(), artifact_dir=absent, connect_fn=_FakeRedis)
        assert result.status == si.BINDING_STATUS_STORE_MISSING
        assert not absent.exists(), "the writer created a private store"
        assert any("refusing to create" in w for w in result.warnings)

        # Initialization is the EXPLICIT operation — only then does a bind succeed.
        si.init_binding_store(absent)
        created = si.write_binding(_binding(), artifact_dir=absent, connect_fn=_FakeRedis)
        assert created.status == si.BINDING_STATUS_CREATED

    def test_concurrent_updates_serialize_on_the_version(self, tmp_path):
        """The reviewer race: two updaters both accepted version 1. The slot lock makes the
        read-check-write one critical section — exactly one upgrade, one named conflict."""
        import threading

        si.write_binding(_binding(), artifact_dir=tmp_path, connect_fn=_FakeRedis)
        outcomes: list[str] = []
        barrier = threading.Barrier(2)

        def updater(name: str) -> None:
            barrier.wait()
            try:
                outcome = si.update_binding_context(
                    "ses_test_1",
                    context={"work_unit": name},
                    expected_version=1,
                    artifact_dir=tmp_path,
                    publish=False,
                )
                outcomes.append(outcome.status)
            except ValueError:
                outcomes.append("conflict")

        threads = [threading.Thread(target=updater, args=(f"work-{i}",)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert sorted(outcomes) == ["conflict", si.BINDING_STATUS_UPDATED], outcomes
        final = si.read_binding("ses_test_1", artifact_dir=tmp_path)
        assert final.binding["context_version"] == 2
        assert final.knowledge_id  # payload + artifact id come from one verified snapshot

    def test_concurrent_first_writes_claim_the_slot_exactly_once(self, tmp_path):
        """O_CREAT|O_EXCL: exactly one `created`; the loser returns the winner's binding."""
        import threading

        results: list[str] = []
        barrier = threading.Barrier(2)

        def writer(request: str) -> None:
            barrier.wait()
            try:
                outcome = si.write_binding(
                    _binding(original_request=request),
                    artifact_dir=tmp_path,
                    connect_fn=_FakeRedis,
                )
                results.append(outcome.status)
            except Exception as exc:  # pragma: no cover - failure detail for the assert
                results.append(f"error: {exc}")

        threads = [
            threading.Thread(target=writer, args=(f"request-{i}",)) for i in range(2)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert sorted(results) == [si.BINDING_STATUS_CREATED, si.BINDING_STATUS_EXISTING], results
        found = si.read_binding("ses_test_1", artifact_dir=tmp_path)
        assert found.status == si.BINDING_STATUS_FOUND
        assert found.binding["original_request"] in ("request-0", "request-1")

    def test_a_copied_slot_is_refused(self, tmp_path):
        si.write_binding(_binding(), artifact_dir=tmp_path, connect_fn=_FakeRedis)
        slot_a = si.binding_slot_path("ses_test_1", artifact_dir=tmp_path)
        slot_b = si.binding_slot_path("ses_other", artifact_dir=tmp_path)
        slot_b.write_bytes(slot_a.read_bytes())  # the foreign-session pointer copy
        result = si.read_binding("ses_other", artifact_dir=tmp_path)
        assert result.status == si.BINDING_STATUS_CORRUPT
        assert any("copied or misplaced" in w for w in result.warnings)

    def test_a_modified_request_is_refused(self, tmp_path):
        written = si.write_binding(_binding(), artifact_dir=tmp_path, connect_fn=_FakeRedis)
        artifact = tmp_path / f"{written.knowledge_id}.json"
        record = json.loads(artifact.read_text())
        payload = json.loads(record["text"])
        payload["original_request"] = "MALICIOUSLY REPLACED"
        # Keep the recorded hash stale — the request-hash check must catch it (the artifact
        # bytes also changed, so the identity recompute is a second guard).
        record["text"] = json.dumps(payload, sort_keys=True)
        artifact.write_text(json.dumps(record, sort_keys=True))
        result = si.read_binding("ses_test_1", artifact_dir=tmp_path)
        assert result.status == si.BINDING_STATUS_CORRUPT
        assert any("modified" in w or "recompute" in w for w in result.warnings)

    def test_legacy_separator_in_the_request_round_trips(self, tmp_path):
        tricky = 'Do the thing || json: {"tricky": true} — and keep it'
        si.write_binding(
            _binding(original_request=tricky), artifact_dir=tmp_path, connect_fn=_FakeRedis
        )
        result = si.read_binding("ses_test_1", artifact_dir=tmp_path)
        assert result.status == si.BINDING_STATUS_FOUND
        assert result.binding["original_request"] == tricky


class TestVersionedContext:
    def test_updates_are_versioned_and_preserve_the_request(self, tmp_path):
        si.write_binding(
            _binding(original_request="ORIGINAL REQUEST"),
            artifact_dir=tmp_path,
            connect_fn=_FakeRedis,
        )
        with pytest.raises(ValueError):
            si.update_binding_context(
                "ses_test_1", context={"work_unit": "x"}, expected_version=7, artifact_dir=tmp_path
            )
        updated = si.update_binding_context(
            "ses_test_1",
            context={
                "work_unit": "repaired unit C",
                "acceptance": {"text": "tests green", "source": "raw"},
                "next_action": "review the PR",
            },
            expected_version=1,
            artifact_dir=tmp_path,
            connect_fn=_FakeRedis,
        )
        assert updated.status == si.BINDING_STATUS_UPDATED
        assert updated.binding["context_version"] == 2
        assert updated.binding["original_request"] == "ORIGINAL REQUEST"
        assert updated.binding["work_unit"] == "repaired unit C"
        assert updated.binding["context_history"][0]["version"] == 1
        # The durable read resolves the NEW version through the atomically replaced slot.
        again = si.read_binding("ses_test_1", artifact_dir=tmp_path)
        assert again.binding["context_version"] == 2
        assert again.binding["original_request"] == "ORIGINAL REQUEST"

    def test_capsule_reflects_the_updated_context(self, tmp_path):
        si.write_binding(_binding(), artifact_dir=tmp_path, connect_fn=_FakeRedis)
        si.update_binding_context(
            "ses_test_1",
            context={"acceptance": {"text": "v2 acceptance", "source": "raw"}},
            expected_version=1,
            artifact_dir=tmp_path,
            connect_fn=_FakeRedis,
        )
        module = _load_session_open("session_open_context_test")
        capsule = module.compose_capsule(
            si.read_binding("ses_test_1", artifact_dir=tmp_path).binding,
            artifact_dir=tmp_path,
            packet={"status": "unavailable", "reason": "test"},
            budget={"verdict": "OK"},
        )
        assert "v2 acceptance" in capsule["text"]


class TestConstraintPreservation:
    def _capsule(self, tmp_path, binding, **kwargs):
        module = _load_session_open("session_open_constraint_test")
        return module.compose_capsule(
            binding,
            artifact_dir=tmp_path,
            packet={"status": "unavailable", "reason": "test"},
            budget={"verdict": "OK"},
            **kwargs,
        )

    def test_acceptance_tail_constraint_survives_with_a_marker(self, tmp_path):
        """The reviewer reproduction: a long criterion ending in NEVER DEPLOY must survive."""
        criterion = ("Requirement: keep the system stable. " * 80) + "NEVER DEPLOY on Fridays."
        capsule = self._capsule(
            tmp_path, _binding(acceptance={"text": criterion, "source": "raw"})
        )
        assert "NEVER DEPLOY on Fridays." in capsule["text"]
        assert "chars omitted" in capsule["text"]
        assert capsule["acceptance"]["truncated"] is True

    def test_a_tiny_bound_still_carries_the_blocker(self, tmp_path):
        """Below the floor, the tail cannot fit — so the composer budgets against the floor
        and records the requested bound separately (reviewer: nonblocking edge)."""
        capsule = self._capsule(
            tmp_path,
            _binding(next_action="N" * 4000, blocker="the real blocker"),
            max_chars=200,
        )
        assert capsule["bounds"]["requested_max_chars"] == 200
        assert capsule["bounds"]["max_chars"] == 600
        assert "the real blocker" in capsule["text"]
        assert "session budget:" in capsule["text"]

    def test_an_oversized_next_action_cannot_evict_the_blocker(self, tmp_path):
        """Each protected tail field is bounded independently: an oversized next action must
        not push the blocker out while the text claims it was preserved."""
        capsule = self._capsule(
            tmp_path,
            _binding(next_action="N" * 4000, blocker="the real blocker"),
            max_chars=8000,
        )
        assert "the real blocker" in capsule["text"]
        assert "N" * 305 not in capsule["text"]  # the next action was bounded with a marker
        assert "next action:" in capsule["text"] and "[truncated:" in capsule["text"]

    def test_the_controlling_tail_survives_the_size_bound(self, tmp_path):
        capsule = self._capsule(
            tmp_path,
            _binding(
                original_request="R" * 4000,
                acceptance={"text": "A" * 4000, "source": "raw"},
                next_action="ship the repair",
                blocker="waiting on review",
            ),
            max_chars=600,
        )
        assert capsule["bounds"]["truncated"] is True
        assert "session budget:" in capsule["text"]
        assert "next action: ship the repair" in capsule["text"]
        assert "blocker: waiting on review" in capsule["text"]
        assert "capsule head truncated" in capsule["text"]
