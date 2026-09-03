"""Tests for the measured scoreboard aggregation (scoreboard.py) — s5a of the

``self_knowledge_layer`` wave (design ``docs/designs/proposed/self_knowledge_layer.md``). The
scoreboard aggregates the s3 wave-verdict records into the measured rows (waves completed,
merge rate, adversarial-finding rate, cost per wave mean/median, time-to-merge, phases per
wave, per-model split) — **recomputed from the records, never hand-written totals**. The
aggregation lives in ``agentic_dynamics/knowledge/scoreboard.py``; the command shell is
``scripts/scoreboard.py`` (``agentic-dynamics scoreboard [--recompute]``).

The DONE_WHEN this file pins:

* N synthetic verdict records aggregate to the correct rows;
* per-model rows split correctly (two models → two rows, each over its own waves);
* recompute is idempotent (same records, same document body — the wall-clock ``generated_at``
  is the only field that may move);
* an empty set yields an empty-but-valid scoreboard — ``waves_completed: 0`` and every
  rate/mean/median ``None`` (no fabricated zeros).

Measured-or-absent is asserted throughout: a merged wave whose record carries no timing
instants contributes nothing to the time-to-merge row and its coverage gap is named, never
silently zero.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentic_dynamics.knowledge import scoreboard as sb
from agentic_dynamics.knowledge import wave_verdict_ingestion as wv
from agentic_dynamics.knowledge.record_factory import record_to_artifact

FLASH = "deepseek/deepseek-v4-flash"
PRO = "deepseek/deepseek-v4-pro"

FLASH_SCOPE = "workload:alpha_wave/job:wf_alpha_wave_deepseek_deepseek_v4_flash"
PRO_SCOPE = "workload:beta_wave/job:wf_beta_wave_deepseek_deepseek_v4_pro"


# ── Fixture helpers ─────────────────────────────────────────────


def _payload(**overrides) -> dict:
    """A canonical s3a wave-verdict payload (the content fields + the model/timing keys).

    The base is a completed-but-unmerged flash wave with no adversarial review. Overrides build
    the richer fixtures (merged waves, pro waves, reviewed waves, timing-bearing waves).
    """
    base = {
        "spec_name": "alpha_wave",
        "run_id": "run-aaaaaaaaaaaa",
        "verdict": "clean",
        "cost": 1.0,
        "phases_total": 5,
        "merge_state": "promotable",
        "residuals": [],
        "narrative": "Wave alpha_wave (run-aaaaaaaaaaaa) came to a clean verdict.",
        "actor": "run",
        "scope": FLASH_SCOPE,
        "model": FLASH,
        "started_at": "2026-09-01T00:00:00+00:00",
        "merged_at": "2026-09-01T06:00:00+00:00",
    }
    base.update(overrides)
    return base


def _derive_payload(ledger: dict, control_row: dict | None = None) -> dict:
    """The payload a REAL s3a derivation produces (drive the real type, not a hand-built body)."""
    record = wv.derive_wave_verdict(ledger, control_row)
    return json.loads(record.text)


def _write_durable(dir_path: Path, record) -> Path:
    """Write ONE record as a durable KB artifact (the s3b emission's durable form)."""
    path = dir_path / f"{record.knowledge_id}.json"
    path.write_bytes(record_to_artifact(record))
    return path


def _write_payload(dir_path: Path, payload: dict, name: str) -> Path:
    """Write ONE bare verdict payload document into the records dir."""
    path = dir_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _flash_ledger(**overrides) -> dict:
    base = {
        "spec_name": "alpha_wave",
        "run_id": "run-aaaaaaaaaaaa",
        "model": FLASH,
        "total_cost_usd": 1.0,
        "phases": [{"phase": f"p{i}"} for i in range(5)],
        "ok": True,
        "state": "succeeded",
        "git_sha": "aaaaaa",
        "ended_at": "2026-09-01T06:00:00+00:00",
    }
    base.update(overrides)
    return base


def _body(document: dict) -> dict:
    return document["body"]


# ── s5 module shape ─────────────────────────────────────────────


def test_scoreboard_is_exported_from_the_knowledge_package():
    from agentic_dynamics.knowledge import scoreboard

    assert scoreboard is sb


def test_extractor_constants_delegate_to_the_s3a_type():
    assert sb.SOURCE_TYPE == "wave_verdict"
    assert sb.EXTRACTOR_VERSION == wv.EXTRACTOR_VERSION == "wave-verdict/v1"
    assert sb.VERDICTS == wv.VERDICTS
    assert sb.ACTOR == "aio"
    assert frozenset({"merged", "published"}) == sb.MERGE_STATES


def test_record_producer_is_aio_at_the_org_root_scope():
    """The actor-layering row: scoreboard producer aio, org:repo (never a cell scope)."""
    from agentic_dynamics.knowledge.session_ingestion import aio_acl_scope

    document, _ = sb.build_scoreboard(Path("/nonexistent"), now=_now())
    producer = document["producer"]
    assert producer["actor"] == "aio"
    assert producer["scope"] == aio_acl_scope("agentic-dynamics")
    assert producer["scope"].startswith("org:")
    assert "/job:" not in producer["scope"] and "self-" not in producer["scope"]


def _now():
    return datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)


# ── Model resolution (deterministic, from the record's own scope) ──


def test_model_is_resolved_from_a_real_derivation_payload():
    """A derive-produced payload has no model key — the model decodes from its OWN scope."""
    ledger = _flash_ledger()
    payload = _derive_payload(ledger)
    assert "model" not in payload
    model, resolved = sb.model_from_payload(payload)
    assert model == FLASH
    assert resolved is True


def test_model_scope_decode_handles_underscored_spec_names():
    """slug(spec + '_' + model) == slug(spec) + '_' + slug(model), so the boundary is exact."""
    payload = _payload(spec_name="self_knowledge_layer", model=FLASH)
    payload["scope"] = wv.wave_verdict_acl_scope("self_knowledge_layer", FLASH)
    del payload["model"]
    model, resolved = sb.model_from_payload(payload)
    assert model == FLASH and resolved is True


def test_an_explicit_model_key_wins_over_the_scope():
    payload = _payload(scope="workload:alpha_wave/job:wf_alpha_wave_something_else")
    model, resolved = sb.model_from_payload(payload)
    assert model == FLASH and resolved is True


def test_an_unresolvable_scope_never_fabricates_a_model():
    payload = _payload(spec_name="weird spec", model="")
    payload["scope"] = "workload:weird spec/job:wf_weird_spec_openai_gpt_5_6_unknown"
    del payload["model"]
    model, resolved = sb.model_from_payload(payload)
    assert model == "openai_gpt_5_6_unknown" or (model == "" and resolved is False)
    assert resolved is False


def test_unresolved_model_waves_are_excluded_from_the_split_and_reported_in_coverage():
    """An unresolved model is never a guessed per-model bucket: the wave counts in the totals,
    is named in coverage, and appears in NO per-model row."""
    good = _payload()
    bad = _payload(
        spec_name="weird spec",
        run_id="run-unresolved",
        scope="workload:weird spec/job:wf_weird_spec_openai_gpt_5_6_unknown",
    )
    del bad["model"]
    body = sb.aggregate_scoreboard([sb.normalize_wave(good), sb.normalize_wave(bad)])
    assert body["totals"]["waves_completed"] == 2
    assert [row["model"] for row in body["per_model"]] == [FLASH]
    assert body["coverage"]["waves_without_model"] == 1
    assert "run-unresolved" in body["coverage"]["unresolved_run_ids"]


# ── The core DONE_WHEN: N records aggregate to the correct rows ──


class TestAggregation:
    def test_three_synthetic_records_aggregate_to_the_correct_rows(self):
        """N=3 (flash promotable clean, flash merged merge-ready, pro failed) -> measured rows.

        Rows checked by hand from the payload fields: 3 waves, 1 merged (rate 1/3), 2 reviewed
        waves with 5 findings (2.5/reviewed wave), cost mean 2.0/median 2.0, phases mean 5.0,
        time-to-merge 6.0h over the one merged wave that carries its instants.
        """
        waves = [
            sb.normalize_wave(_payload()),  # flash, promotable, clean, no review
            sb.normalize_wave(
                _payload(
                    run_id="run-bbbbbbbbbbbb",
                    verdict="merge-ready",
                    cost=2.0,
                    phases_total=8,
                    merge_state="merged",
                    adversarial_findings_count=2,
                )
            ),
            sb.normalize_wave(
                _payload(
                    spec_name="beta_wave",
                    run_id="run-cccccccccccc",
                    verdict="not",
                    cost=3.0,
                    phases_total=2,
                    merge_state="failed",
                    scope=PRO_SCOPE,
                    model=PRO,
                    adversarial_findings_count=3,
                )
            ),
        ]
        body = sb.aggregate_scoreboard(waves)
        totals = body["totals"]
        assert totals["waves_completed"] == 3
        assert totals["waves_merged"] == 1
        assert totals["merge_rate"] == pytest.approx(1 / 3)
        assert totals["waves_reviewed"] == 2
        assert totals["adversarial_findings_total"] == 5
        assert totals["adversarial_findings_per_reviewed_wave"] == pytest.approx(2.5)
        assert totals["cost_per_wave_usd"]["mean"] == pytest.approx(2.0)
        assert totals["cost_per_wave_usd"]["median"] == pytest.approx(2.0)
        assert totals["phases_per_wave"]["mean"] == pytest.approx(5.0)
        assert totals["phases_per_wave"]["median"] == pytest.approx(5.0)
        assert totals["time_to_merge_hours"] == {
            "mean": pytest.approx(6.0),
            "median": pytest.approx(6.0),
            "merged_with_timing": 1,
        }
        # every total traces to the per-wave rows (measured, never hand-written)
        assert len(body["waves"]) == 3

    def test_per_model_rows_split_correctly(self):
        """Two models -> two per-model rows, each over its own waves with its own rows."""
        waves = [
            sb.normalize_wave(_payload()),
            sb.normalize_wave(
                _payload(
                    run_id="run-bbbbbbbbbbbb",
                    verdict="merge-ready",
                    cost=2.0,
                    phases_total=8,
                    merge_state="merged",
                    adversarial_findings_count=2,
                )
            ),
            sb.normalize_wave(
                _payload(
                    spec_name="beta_wave",
                    run_id="run-cccccccccccc",
                    verdict="not",
                    cost=3.0,
                    phases_total=2,
                    merge_state="failed",
                    scope=PRO_SCOPE,
                    model=PRO,
                    adversarial_findings_count=3,
                )
            ),
        ]
        body = sb.aggregate_scoreboard(waves)
        by_model = {row["model"]: row for row in body["per_model"]}
        assert set(by_model) == {FLASH, PRO}
        flash = by_model[FLASH]
        assert flash["waves"] == 2
        assert flash["merged"] == 1
        assert flash["merge_rate"] == pytest.approx(0.5)
        assert flash["waves_reviewed"] == 1
        assert flash["adversarial_findings_per_reviewed_wave"] == pytest.approx(2.0)
        assert flash["cost_per_wave_usd"]["mean"] == pytest.approx(1.5)
        assert flash["cost_per_wave_usd"]["median"] == pytest.approx(1.5)
        pro_row = by_model[PRO]
        assert pro_row["waves"] == 1
        assert pro_row["merged"] == 0
        assert pro_row["merge_rate"] == pytest.approx(0.0)
        assert pro_row["waves_reviewed"] == 1
        assert pro_row["adversarial_findings_per_reviewed_wave"] == pytest.approx(3.0)
        assert pro_row["cost_per_wave_usd"]["mean"] == pytest.approx(3.0)

    def test_median_is_the_even_list_average(self):
        waves = [
            sb.normalize_wave(_payload(run_id=f"run-median{i}", cost=c))
            for i, c in enumerate((1.0, 2.0, 3.0, 4.0))
        ]
        body = sb.aggregate_scoreboard(waves)
        cost = body["totals"]["cost_per_wave_usd"]
        assert cost["mean"] == pytest.approx(2.5)
        assert cost["median"] == pytest.approx(2.5)

    def test_a_wave_without_a_review_never_reads_as_a_zero_finding_review(self):
        """adversarial_findings_count present ONLY with a review — an unreviewed clean wave is
        not a zero-finding review, so it is excluded from the per-reviewed-wave rate."""
        waves = [
            sb.normalize_wave(_payload(adversarial_findings_count=0)),  # reviewed, clean sweep
            sb.normalize_wave(_payload(run_id="run-bbbbbbbbbbbb")),  # unreviewed
        ]
        body = sb.aggregate_scoreboard(waves)
        totals = body["totals"]
        assert totals["waves_reviewed"] == 1
        assert totals["adversarial_findings_total"] == 0
        assert totals["adversarial_findings_per_reviewed_wave"] == pytest.approx(0.0)
        assert totals["review_coverage"] == pytest.approx(0.5)

    def test_multiple_versions_of_one_run_collapse_to_the_waves_current_standing(self):
        """The s3a version chain: a merged re-derivation supersedes its promotable version —
        one run must never count as two waves or as both unmerged and merged."""
        promotable = sb.normalize_wave(_payload(merge_state="promotable", cost=1.0))
        merged = sb.normalize_wave(
            _payload(verdict="merge-ready", merge_state="merged", cost=1.0)
        )
        body = sb.aggregate_scoreboard([promotable, merged])
        assert body["totals"]["waves_completed"] == 1
        assert body["totals"]["waves_merged"] == 1
        assert len(body["waves"]) == 1
        assert body["waves"][0]["merge_state"] == "merged"

    def test_a_merged_wave_without_timing_contributes_no_fabricated_latency(self):
        """Measured-or-absent: a merged wave whose record carries no timing instants is not a
        zero-hour merge — the timing row stays absent and the coverage names the gap."""
        payload = _payload(merge_state="merged")
        payload.pop("started_at")
        payload.pop("merged_at")
        body = sb.aggregate_scoreboard([sb.normalize_wave(payload)])
        ttm = body["totals"]["time_to_merge_hours"]
        assert ttm["mean"] is None and ttm["median"] is None
        assert ttm["merged_with_timing"] == 0
        assert body["coverage"]["merged_timing_gap"] == 1


# ── The read seam (durable artifacts + bare payload docs) ────────


class TestReadSeam:
    def test_durable_wave_verdict_artifacts_are_aggregated(self, tmp_path):
        """The s3b durable form (record_to_artifact of a REAL derivation) is the aggregation's
        natural input: write two derived records, aggregate the dir, get two waves."""
        rec_a = wv.build_wave_verdict_record(_flash_ledger())
        rec_b = wv.build_wave_verdict_record(
            _flash_ledger(
                run_id="run-bbbbbbbbbbbb",
                spec_name="beta_wave",
                model=PRO,
                total_cost_usd=3.0,
                ok=False,
                state="failed",
            ),
            control_row={
                "run_id": "run-bbbbbbbbbbbb",
                "spec_name": "beta_wave",
                "state": "failed",
                "model": PRO,
                "cost_usd": 3.0,
            },
        )
        _write_durable(tmp_path, rec_a)
        _write_durable(tmp_path, rec_b)
        document, warnings = sb.build_scoreboard(tmp_path, now=_now())
        assert warnings == []
        assert document["body"]["totals"]["waves_completed"] == 2
        models = {w["model"] for w in document["body"]["waves"]}
        assert models == {FLASH, PRO}
        # the real payloads decode their model from the scope (no explicit model key)
        assert all(w["model_resolved"] for w in document["body"]["waves"])

    def test_bare_payload_documents_are_aggregated(self, tmp_path):
        _write_payload(tmp_path, _payload(), "w1.json")
        _write_payload(
            tmp_path,
            _payload(run_id="run-bbbbbbbbbbbb", merge_state="merged", model=PRO),
            "w2.json",
        )
        document, warnings = sb.build_scoreboard(tmp_path, now=_now())
        assert warnings == []
        assert document["body"]["totals"]["waves_completed"] == 2
        assert document["body"]["totals"]["waves_merged"] == 1

    def test_foreign_artifacts_are_skipped_and_anomalies_are_warned(self, tmp_path):
        _write_payload(tmp_path, _payload(), "w1.json")
        (tmp_path / "unrelated.json").write_text(json.dumps({"fact": 1}), encoding="utf-8")
        (tmp_path / "other_org.json").write_text(
            json.dumps(
                {
                    "extractor_version": "wave-verdict/v1",
                    "repository_id": "some-other-org",
                    "text": json.dumps(_payload()),
                }
            ),
            encoding="utf-8",
        )
        anomaly = {
            "extractor_version": "wave-verdict/v1",
            "repository_id": "agentic-dynamics",
            "text": "{not json",
        }
        (tmp_path / "anomaly.json").write_text(json.dumps(anomaly), encoding="utf-8")
        document, warnings = sb.build_scoreboard(tmp_path, now=_now())
        assert document["body"]["totals"]["waves_completed"] == 1
        assert len(warnings) == 1
        assert "anomaly.json" in warnings[0]

    def test_a_missing_records_dir_is_an_empty_but_valid_input(self, tmp_path):
        document, warnings = sb.build_scoreboard(tmp_path / "does-not-exist", now=_now())
        assert warnings == []
        assert document["body"]["totals"]["waves_completed"] == 0


# ── The DONE_WHEN edges: empty-but-valid + idempotent recompute ──


class TestDoneWhen:
    def test_an_empty_set_yields_an_empty_but_valid_scoreboard(self, tmp_path):
        """Empty record set -> waves_completed 0 and NO fabricated zeros: every rate/mean/
        median is None (an empty mean is not 0.0), the rows arrays are empty."""
        document, warnings = sb.build_scoreboard(tmp_path, now=_now())
        assert warnings == []
        totals = document["body"]["totals"]
        assert totals["waves_completed"] == 0
        assert totals["waves_merged"] == 0
        assert totals["merge_rate"] is None
        assert totals["waves_reviewed"] == 0
        assert totals["adversarial_findings_total"] == 0
        assert totals["adversarial_findings_per_reviewed_wave"] is None
        assert totals["cost_per_wave_usd"] == {
            "mean": None,
            "median": None,
            "n": 0,
        }
        assert totals["phases_per_wave"] == {
            "mean": None,
            "median": None,
            "n": 0,
        }
        assert totals["time_to_merge_hours"]["mean"] is None
        assert totals["time_to_merge_hours"]["median"] is None
        assert document["body"]["per_model"] == []
        assert document["body"]["waves"] == []
        assert document["body"]["coverage"]["waves"] == 0
        assert document["schema"] == "scoreboard/v1"
        assert document["producer"]["scope"].startswith("org:")

    def test_recompute_is_idempotent(self, tmp_path):
        """Same records in -> same document body out: recompute twice, the totals/rows are
        byte-identical (only the wall-clock generated_at may move)."""
        _write_payload(tmp_path, _payload(), "w1.json")
        _write_payload(
            tmp_path,
            _payload(run_id="run-bbbbbbbbbbbb", merge_state="merged", cost=2.0),
            "w2.json",
        )
        first, _ = sb.build_scoreboard(tmp_path, now=_now())
        second, _ = sb.build_scoreboard(tmp_path, now=_now())
        assert first["body"] == second["body"]
        assert first["generated_at"] == second["generated_at"]  # pinned clock

    def test_scoreboard_recompute_without_a_pinned_clock_differs_only_in_generated_at(
        self, tmp_path
    ):
        _write_payload(tmp_path, _payload(), "w1.json")
        first, _ = sb.build_scoreboard(tmp_path)
        second, _ = sb.build_scoreboard(tmp_path)
        assert first["body"] == second["body"]
        assert first.keys() == second.keys()


# ── The command shell (scripts/scoreboard.py) ───────────────────


def _load_script(rel_path: str, name: str):
    import importlib.util

    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(name, root / rel_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def scoreboard_cli():
    return _load_script("scripts/scoreboard.py", "scoreboard_under_test")


class TestCommand:
    def test_json_recompute_renders_the_measured_rows(
        self, tmp_path, scoreboard_cli, capsys
    ):
        _write_payload(tmp_path, _payload(), "w1.json")
        _write_payload(
            tmp_path,
            _payload(run_id="run-bbbbbbbbbbbb", merge_state="merged", cost=2.0),
            "w2.json",
        )
        out = tmp_path / "out" / "scoreboard.json"
        rc = scoreboard_cli.main(
            ["--records-dir", str(tmp_path), "--out", str(out), "--json"]
        )
        assert rc == 0
        assert not out.exists()  # --json implies dry-run: nothing written
        printed = json.loads(capsys.readouterr().out)
        assert printed["schema"] == "scoreboard/v1"
        assert printed["body"]["totals"]["waves_completed"] == 2
        assert printed["body"]["totals"]["waves_merged"] == 1

    def test_recompute_writes_the_durable_document_and_reuse_renders_it(
        self, tmp_path, scoreboard_cli, capsys
    ):
        _write_payload(tmp_path, _payload(), "w1.json")
        out = tmp_path / "out" / "scoreboard.json"
        rc = scoreboard_cli.main(["--records-dir", str(tmp_path), "--out", str(out)])
        assert rc == 0
        assert out.is_file()
        stored = json.loads(out.read_text(encoding="utf-8"))
        assert stored["body"]["totals"]["waves_completed"] == 1

        # Without --recompute (and no records dir), the stored document is rendered.
        rc = scoreboard_cli.main(["--out", str(out)])
        assert rc == 0
        rendered = capsys.readouterr().out
        assert "1 wave(s) completed" in rendered
        assert "stored document" in rendered

    def test_recompute_is_idempotent_at_the_command_boundary(
        self, tmp_path, scoreboard_cli
    ):
        _write_payload(tmp_path, _payload(), "w1.json")
        _write_payload(
            tmp_path,
            _payload(run_id="run-bbbbbbbbbbbb", merge_state="merged", model=PRO, cost=2.0),
            "w2.json",
        )
        out = tmp_path / "out" / "scoreboard.json"
        scoreboard_cli.main(["--records-dir", str(tmp_path), "--out", str(out)])
        first = json.loads(out.read_text(encoding="utf-8"))
        scoreboard_cli.main(
            ["--recompute", "--records-dir", str(tmp_path), "--out", str(out)]
        )
        second = json.loads(out.read_text(encoding="utf-8"))
        assert first["body"] == second["body"]

    def test_empty_records_dir_writes_an_empty_but_valid_document(
        self, tmp_path, scoreboard_cli
    ):
        out = tmp_path / "out" / "scoreboard.json"
        rc = scoreboard_cli.main(["--records-dir", str(tmp_path), "--out", str(out)])
        assert rc == 0
        stored = json.loads(out.read_text(encoding="utf-8"))
        assert stored["body"]["totals"]["waves_completed"] == 0
        assert stored["body"]["totals"]["merge_rate"] is None
