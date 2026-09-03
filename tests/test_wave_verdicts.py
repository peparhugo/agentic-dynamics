"""Tests for the wave-verdict record type (wave_verdict_ingestion) — s3a of the
self_knowledge_layer wave.

Covers the record-type cases (the s3a scope fence — type ONLY, the emission hook is s3b):
``derive_wave_verdict`` derives ONE ``source_type=wave_verdict`` record from a run ledger + its
control-db row + (when it exists) the adversarial review artifact, carrying the deliverable's
fixed content shape {spec_name, run_id, verdict, cost, phases_total, merge_state, residuals[],
narrative, actor, scope} plus ``adversarial_findings_count`` PRESENT ONLY when a review doc
exists. The type cases assert: the registered source_type (observation-family DERIVED/[C]); the
actor (``run``) + workload/job scope carriage (structural + self-describing in the body); the
round trip through record_to_artifact / record_to_event / extract_record; rerun-safe identity
(same inputs -> same knowledge_id; a control-state advance re-keys knowledge_id but not
entity_id); the namespace separation from the session/decision/k2-wave families; and the two
DONE_WHEN derivations — findings count present/absent with and without a review artifact, and
merge_state reflecting the control-db row.

The fixtures model the last completed wave (kb_finding_layer, run-77f7b899f4f8): its run ledger
shape (state succeeded, cost, phase list), its control-db ``runs`` row (state promotable), and
the shape of its adversarial review doc (docs/reviews/kb_finding_layer_adversarial.md) — all
synthetic, so the tests are hermetic.

The s3b emission cases (the bottom section) drive the run-completion EMISSION hook — the
composition root's terminal write in ``scripts/run_workflow.py``, where the ledger + control-db
terminal write land. Default-on (no flag arms it) and best-effort under the same ``_derived``
fence as the spec/fact derivations. The s3b DONE_WHEN: a synthetic completed run emits its
verdict with the measured fields; a failed run emits its failed verdict. These cases run the
REAL ``_control_terminal_write`` hermetically: ``run_workflow`` is loaded fresh via ``importlib``
(the same technique ``test_fact_auto_emit.py`` uses — it is not a package), the control db + KB
artifact dir + registry index are redirected to ``tmp_path``, the knowledge stream is a fake,
and the spec-index read is stubbed, so the only thing the terminal write can enqueue is the
wave verdict.
"""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from agentic_dynamics.control.control_db import (
    ControlDB,
    RunState,
)
from agentic_dynamics.experiment.experiment_spec import (
    ExperimentSpec,
    StopSpec,
    Workflow,
)
from agentic_dynamics.knowledge import wave_verdict_ingestion as wv
from agentic_dynamics.knowledge.knowledge import (
    SOURCE_TYPES,
    Authority,
    message_family,
)
from agentic_dynamics.knowledge.knowledge_ingestion import (
    REPOSITORY_ID,
    extract_record,
    record_to_artifact,
    record_to_event,
)
from agentic_dynamics.runtime.workflow_runner import (
    PhaseResult,
    WorkflowRunResult,
)

ROOT = Path(__file__).resolve().parent.parent


def _ledger(**overrides) -> dict:
    """A synthetic run ledger — the kb_finding_layer run's recorded shape (s3a DONE_WHEN)."""
    base = {
        "spec_name": "kb_finding_layer",
        "spec_id": "kb_finding_layer@0.1",
        "run_id": "run-77f7b899f4f8",
        "model": "deepseek/deepseek-v4-flash",
        "state": "succeeded",
        "ok": True,
        "git_sha": "00d15dbf3",
        "total_cost_usd": 1.469705,
        "attempt_count": 8,
        "phases": [{"phase": f"k{i}_phase", "status": "ok"} for i in range(8)],
        "ended_at": "2026-09-03T18:40:28.748198+00:00",
    }
    base.update(overrides)
    return base


def _control_row(**overrides) -> dict:
    """A synthetic control-db ``runs`` row — the kb_finding_layer row's recorded shape."""
    base = {
        "run_id": "run-77f7b899f4f8",
        "spec_name": "kb_finding_layer",
        "candidate_sha": "00d15dbf3",
        "state": "promotable",
        "model": "deepseek/deepseek-v4-flash",
        "cost_usd": 1.469705,
        "ledger_path": "experiments/results/workflows/kb_finding_layer/20260903T184028Z.json",
        "ended_at": "2026-09-03T18:40:28.748198+00:00",
    }
    base.update(overrides)
    return base


def _review_doc(**overrides) -> str:
    """A synthetic adversarial review artifact shaped like the kb_finding_layer review doc.

    Carries the merge-ready verdict signal, a three-row finding table (F1-F3), and an accepted
    limitations section — the shapes the deterministic parser reads.
    """
    text = """---
status: accepted
kind: adversarial_review
spec: kb_finding_layer
---
# kb_finding_layer — adversarial review

**Verdict: PASS (merge-ready).** The core claim held under independent probe.
Three findings are recorded (all RECORD-level accepted limitations).

## 1. Findings

| # | Attack | Disposition | Reasoning |
|---|---|---|---|
| F1 | k2 backfill is corpus-sensitive | **RECORD** (accepted limitation) | re-running against an advanced corpus mints parallel records |
| F2 | k5 narrator has 0 live records | **RECORD** (forward-only) | not yet observed on a live shift |
| F3 | 3 publication gates are RED | **RECORD** (pre-existing) | pre-existing drift at the merge base |

## 2. Accepted limitations

The residual scope is the version-chain consequence of F1 and the forward-only narrator of F2.
"""
    text = overrides.pop("_text", text)
    # Allow callers to inject finding-table rows / override whole text.
    if "_text" in overrides:
        text = overrides.pop("_text")
    if "rows" in overrides:
        text = text.replace(
            "| F3 | 3 publication gates are RED | **RECORD** (pre-existing) | pre-existing drift at the merge base |",
            overrides.pop("rows"),
        )
    if overrides:
        raise TypeError(f"unexpected review overrides: {sorted(overrides)}")
    return text


def _payload(record) -> dict:
    return json.loads(record.text)


# ── Extractor contract constants ────────────────────────────────


def test_extractor_constants():
    assert wv.SOURCE_TYPE == "wave_verdict"
    assert wv.EXTRACTOR_VERSION == "wave-verdict/v1"
    assert wv.ACTOR == "run"
    assert wv.REVISION_FALLBACK == "wave-verdict/unrevisioned"
    assert wv.VERDICTS == ("merge-ready", "not", "clean")
    # Registered in the one vocabulary table as an observation-family DERIVED/[C] row: a wave
    # verdict states what a run's completion was (never an instruction to act) and is a
    # deterministic synthesis over measured + advisory inputs, so it can feed the scoreboard but
    # never masquerade as an independent measurement.
    assert wv.SOURCE_TYPE in SOURCE_TYPES
    assert SOURCE_TYPES["wave_verdict"].authority is Authority.DERIVED
    assert SOURCE_TYPES["wave_verdict"].evidence_class == "[C]"
    assert message_family("wave_verdict") == "observation"


def test_wave_verdict_ingestion_is_exported_from_the_knowledge_package():
    from agentic_dynamics.knowledge import wave_verdict_ingestion

    assert wave_verdict_ingestion is wv


# ── Provenance + the actor/scope carriage ───────────────────────


def test_record_provenance_is_derived_c_like_the_registered_nominal():
    record = wv.derive_wave_verdict(_ledger(), _control_row())
    assert record.source_type == "wave_verdict"
    assert record.authority is Authority.DERIVED
    assert record.evidence_class == "[C]"


def test_record_carries_run_actor_and_its_own_workload_job_scope():
    record = wv.derive_wave_verdict(_ledger(), _control_row())
    # Scope is structural on the record: the org id as repository_id (same corpus anchoring the
    # session/decision records, so an org-root read resolves it) and the run's OWN workload/job
    # scope as acl_scope — the design actor table's "workload:<spec>/job:<cell> (its own)", NOT
    # an AIO org-root scope and NOT the corpus's "public" acl.
    assert record.repository_id == REPOSITORY_ID
    assert record.acl_scope == "workload:kb_finding_layer/job:wf_kb_finding_layer_deepseek_deepseek_v4_flash"
    # And self-describing in the body: actor + scope keys are part of the hashed payload.
    payload = _payload(record)
    assert payload["actor"] == "run"
    assert payload["scope"] == record.acl_scope


def test_scope_helper_names_the_run_own_job():
    # wf_<spec>_<model> is the run's own job cell in the control plane (its ledger attempts carry
    # it as job_id) — re-declared here without importing the reducers.
    assert wv.job_cell_id("kb_finding_layer", "deepseek/deepseek-v4-flash") == (
        "wf_kb_finding_layer_deepseek_deepseek_v4_flash"
    )
    assert wv.wave_verdict_acl_scope("kb_finding_layer", "deepseek/deepseek-v4-flash") == (
        "workload:kb_finding_layer/job:wf_kb_finding_layer_deepseek_deepseek_v4_flash"
    )


def test_cell_scoped_retrieval_excludes_the_wave_verdict_record():
    # Actor layering, deterministic at the type: the record's repository_id is the org id, so the
    # retrieval hard pre-filter (scope_excluded) excludes it from any cell/workload query — a
    # self-* cell scope or a foreign workload never equals the org id, so another workload's
    # agents cannot resolve this run's verdict. Only an explicit org-root read sees it.
    from agentic_dynamics.knowledge.retrieval import scope_excluded

    record = wv.derive_wave_verdict(_ledger(), _control_row())
    assert scope_excluded(record.repository_id, requested_scope="self-wt_wave4")
    assert scope_excluded(
        record.repository_id,
        requested_scope="workload:authoring_product_aio/job:wf_authoring_product_aio_deepseek_deepseek_v4_flash",
    )
    # The AIO/controller at the org root resolves it (empty candidate scope semantics unchanged).
    assert not scope_excluded(record.repository_id, requested_scope="")
    assert not scope_excluded("", requested_scope="agentic-dynamics")


# ── The deliverable content fields round-trip ───────────────────


def test_content_fields_round_trip_through_artifact_and_event():
    record = wv.derive_wave_verdict(_ledger(), _control_row(), _review_doc())

    artifact = record_to_artifact(record)
    event = record_to_event(record)
    extracted = extract_record(event, artifact)

    assert extracted.knowledge_id == record.knowledge_id
    assert extracted.content_hash == record.content_hash
    assert extracted.entity_id == record.entity_id
    assert extracted.acl_scope == record.acl_scope
    assert extracted.text == record.text

    payload = _payload(extracted)
    assert payload["spec_name"] == "kb_finding_layer"
    assert payload["run_id"] == "run-77f7b899f4f8"
    assert payload["verdict"] == "merge-ready"
    assert payload["cost"] == 1.469705
    assert payload["phases_total"] == 8
    assert payload["merge_state"] == "promotable"
    assert payload["adversarial_findings_count"] == 3
    assert isinstance(payload["residuals"], list) and payload["residuals"]
    assert payload["actor"] == "run"
    assert payload["scope"] == record.acl_scope
    # The narrative is the one-paragraph "what happened and why".
    narrative = payload["narrative"]
    assert isinstance(narrative, str) and len(narrative) > 60
    assert "kb_finding_layer" in narrative and "run-77f7b899f4f8" in narrative

    # The standard pointer contract: content_hash covers the artifact, observed_at is the run's
    # own completion instant (not the producer clock), source_revision is the candidate the
    # verdict judges.
    assert event.knowledge_id == record.knowledge_id
    assert event.operation == "upsert"
    assert event.content_hash == hashlib.sha256(artifact).hexdigest()
    assert event.observed_at == "2026-09-03T18:40:28.748198+00:00"
    assert extracted.observed_at == "2026-09-03T18:40:28.748198+00:00"
    assert event.source_revision == record.commit_sha == "00d15dbf3"


def test_full_dict_round_trip_is_lossless():
    from agentic_dynamics.knowledge.knowledge import KnowledgeRecord

    record = wv.derive_wave_verdict(_ledger(), _control_row(), _review_doc())
    restored = KnowledgeRecord.from_dict(record.to_dict())
    assert restored == record


def test_derive_and_build_delegate_to_the_same_record():
    a = wv.derive_wave_verdict(_ledger(), _control_row(), _review_doc())
    b = wv.build_wave_verdict_record(_ledger(), _control_row(), _review_doc())
    for attr in (
        "knowledge_id",
        "entity_id",
        "content_hash",
        "source_uri",
        "text",
        "logical_locator",
        "acl_scope",
        "repository_id",
    ):
        assert getattr(a, attr) == getattr(b, attr)


# ── The two DONE_WHEN derivations ───────────────────────────────


def test_with_a_review_artifact_the_findings_count_is_present():
    # DONE_WHEN half 1a: with the adversarial review doc, adversarial_findings_count is derived
    # and present, residuals are populated from the doc, and the verdict is classified from the
    # review's merge-ready signal (not re-derived by hand).
    record = wv.derive_wave_verdict(_ledger(), _control_row(), _review_doc())
    payload = _payload(record)
    assert payload["adversarial_findings_count"] == 3
    assert payload["residuals"]
    assert payload["verdict"] == "merge-ready"


def test_without_a_review_artifact_the_findings_count_is_absent():
    # DONE_WHEN half 1b: without the adversarial review doc the findings-count key is OMITTED
    # (never a fabricated 0 — a run without a review doc is not a review that recorded zero
    # findings), residuals default to [], and the verdict falls back to the run's own green
    # disposition.
    record = wv.derive_wave_verdict(_ledger(), _control_row())
    payload = _payload(record)
    assert "adversarial_findings_count" not in payload
    assert payload["residuals"] == []
    assert payload["verdict"] == "clean"


def test_merge_state_reflects_the_control_db_row():
    # DONE_WHEN half 2: merge_state is the control-db row's state read verbatim — the control
    # plane's measured answer to "where does this run stand relative to the merge?".
    assert _payload(wv.derive_wave_verdict(_ledger(), _control_row()))["merge_state"] == "promotable"
    assert (
        _payload(wv.derive_wave_verdict(_ledger(), _control_row(state="merged")))["merge_state"]
        == "merged"
    )
    assert (
        _payload(wv.derive_wave_verdict(_ledger(), _control_row(state="published")))["merge_state"]
        == "published"
    )
    assert (
        _payload(wv.derive_wave_verdict(_ledger(), _control_row(state="failed")))["merge_state"]
        == "failed"
    )


def test_merge_state_falls_back_to_a_ledger_mirror_when_no_control_row():
    # No control-db row: a local mirror of control_db.run_state_from_ledger_state derives the
    # same control vocabulary from the ledger's terminal label (succeeded -> promotable — phases
    # passing authorises a promotion, it does not ARE one).
    record = wv.derive_wave_verdict(_ledger(), None)
    assert _payload(record)["merge_state"] == "promotable"
    assert (
        _payload(wv.derive_wave_verdict(_ledger(state="failed", ok=False), None))["merge_state"]
        == "failed"
    )
    assert (
        _payload(
            wv.derive_wave_verdict(_ledger(state="cancelled", ok=False), None)
        )["merge_state"]
        == "cancelled"
    )


def test_a_failed_run_emits_its_failed_verdict():
    # A failure is a verdict, not a silence: a failed run without a review reads "not", and its
    # control state reflects the row even when the run did not reach the adversarial phase.
    record = wv.derive_wave_verdict(_ledger(state="failed", ok=False), _control_row(state="failed"))
    payload = _payload(record)
    assert payload["verdict"] == "not"
    assert payload["merge_state"] == "failed"
    assert "adversarial_findings_count" not in payload
    assert payload["residuals"] == []


def test_quoted_fail_evidence_never_overrides_the_docs_own_pass_statement():
    # The real fixture doc (kb_finding_layer_adversarial.md — the last completed wave's review)
    # states "**Verdict: PASS (merge-ready)**" and THEN quotes other waves' backfilled records
    # whose text contains "Verdict: FAIL" / "not merge-ready". A whole-text scan would let that
    # quoted FAIL override the doc's own PASS. The classifier reads the doc's OWN bold verdict
    # statement first, so this doc's verdict is its own merge-ready, never the quotes'.
    text = """---
status: accepted
kind: adversarial_review
spec: kb_finding_layer
---
# kb_finding_layer k7 — independent adversarial review

**Verdict: PASS (merge-ready).** Every claim was re-derived; none falsified.

## 3. Findings

| # | Attack | Disposition | Reasoning |
|---|---|---|---|
| F1 | k2 backfill is rerun-safe | **RECORD** (accepted limitation) | corpus-sensitive |
| F2 | k5 narrator forward-only | **RECORD** | 0 live records yet |
| F3 | 3 gates are RED | **RECORD** (pre-existing) | pre-existing drift |

The control_db_evidence backfill artifact has `verdict not` and its conclusion reads
`Verdict: FAIL — merge-blocked on the mis-specified run criterion`; those are QUOTED from a
different wave's record and must not flip THIS doc's verdict.
"""
    assert wv.classify_wave_verdict(text, run_succeeded=True, control_state="promotable") == (
        "merge-ready"
    )
    # A doc whose OWN statement is FAIL still reads not — the statement, not the quotes, decides.
    failing = text.replace("**Verdict: PASS (merge-ready).**", "**Verdict: FAIL — merge-blocked.**")
    assert wv.classify_wave_verdict(failing, run_succeeded=True, control_state="promotable") == "not"


# ── Rerun-safe identity ─────────────────────────────────────────


def test_knowledge_id_is_rerun_safe_same_inputs_same_id():
    first = wv.derive_wave_verdict(_ledger(), _control_row(), _review_doc())
    second = wv.derive_wave_verdict(_ledger(), _control_row(), _review_doc())
    assert second.knowledge_id == first.knowledge_id
    assert second.entity_id == first.entity_id
    assert second.content_hash == first.content_hash


def test_a_control_state_advance_rekeys_knowledge_id_but_not_entity_id():
    # The same run promoted (promotable -> merged) is a NEW version of the SAME run slot: content
    # changes (merge_state, narrative) so knowledge_id re-keys, while entity_id holds — exactly
    # the version chain the scoreboard needs.
    promotable = wv.derive_wave_verdict(_ledger(), _control_row())
    merged = wv.derive_wave_verdict(_ledger(), _control_row(state="merged"))
    assert merged.entity_id == promotable.entity_id
    assert merged.knowledge_id != promotable.knowledge_id
    assert merged.content_hash != promotable.content_hash
    assert _payload(merged)["merge_state"] == "merged"
    assert _payload(promotable)["merge_state"] == "promotable"


def test_a_different_run_is_a_different_entity():
    other = wv.derive_wave_verdict(_ledger(run_id="run-abc123def456"), _control_row())
    first = wv.derive_wave_verdict(_ledger(), _control_row())
    assert other.entity_id != first.entity_id
    assert other.knowledge_id != first.knowledge_id
    assert other.logical_locator == "run-abc123def456"


def test_identity_is_namespace_distinct_from_decision_and_session():
    from agentic_dynamics.knowledge.decision_ingestion import derive_decision_record
    from agentic_dynamics.knowledge.session_ingestion import derive_session_record

    verdict = wv.derive_wave_verdict(_ledger(), _control_row())
    decision = derive_decision_record(
        {
            "what": "park the fleet",
            "why": "dormant lane",
            "alternatives": [],
            "category": "park",
            "decided_at": "2026-09-03T12:00:00+00:00",
        }
    )
    session = derive_session_record(
        {
            "session_date": "2026-09-03",
            "slug": verdict.logical_locator,  # same locator string, different family
            "waves_run": [],
        }
    )
    assert verdict.source_uri.startswith("wave_verdict:")
    assert verdict.extractor_version == "wave-verdict/v1"
    assert decision.source_uri.startswith("decision:")
    assert session.source_uri.startswith("session:")
    assert verdict.entity_id != decision.entity_id
    assert verdict.entity_id != session.entity_id
    assert verdict.knowledge_id != decision.knowledge_id
    assert verdict.knowledge_id != session.knowledge_id


# ── Validation ──────────────────────────────────────────────────


def test_missing_spec_name_raises_value_error():
    # Both inputs cleared: the control row legitimately identifies the run when the ledger omits
    # the field, so a genuine absence must be empty everywhere.
    with pytest.raises(ValueError, match="spec_name"):
        wv.derive_wave_verdict(_ledger(spec_name=""), _control_row(spec_name=""))


def test_missing_run_id_raises_value_error():
    with pytest.raises(ValueError, match="run_id"):
        wv.derive_wave_verdict(_ledger(run_id=None), _control_row(run_id=""))


def test_missing_measured_cost_raises_value_error():
    # An unknown cost is never treated as zero — the record refuses rather than mint a 0.0 that
    # would poison the scoreboard's per-wave average.
    with pytest.raises(ValueError, match="cost"):
        wv.derive_wave_verdict(_ledger(total_cost_usd=None), _control_row(cost_usd=None))


# ── s3b — the run-completion emission cases (scripts/run_workflow.py's terminal write) ──
# ════════════════════════════════════════════════════════════════════════════════════════════
#
# The s3b DONE_WHEN: every completed spec run emits its wave-verdict narrative at the
# run-completion path (the composition root where the ledger + control-db terminal write land);
# a FAILED run still emits (a failure is a verdict, not a silence). Default-on — no flag arms
# it — and best-effort under the same ``_derived`` fence as the spec/fact derivations.
#
# These cases drive the REAL ``scripts/run_workflow._control_terminal_write`` hermetically:
# the module is loaded fresh via ``importlib`` (the technique ``test_fact_auto_emit.py`` uses —
# it is not a package), the control db + KB artifact dir + registry index are redirected under
# ``tmp_path``, the knowledge stream is a fake, and the spec-index read is stubbed so the ONLY
# payload the terminal write can enqueue is the wave verdict (``no_fact_emit`` is True). Nothing
# touches the live KB or a real Redis.

EMIT_NOW = "2026-09-03T18:40:28.748198+00:00"


def _load_script(rel_path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def rw(tmp_path, monkeypatch):
    """A fresh ``run_workflow`` module, hermetically re-rooted at ``tmp_path``.

    ``ROOT`` is rebound so the s3b review-doc read (``docs/reviews/<spec>_adversarial.md``)
    resolves under the test's own tree; every other ROOT consumer in the exercised path
    (the spec index) is stubbed below.
    """
    module = _load_script("scripts/run_workflow.py", "run_workflow_under_test_wv")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    return module


def _emit_spec(name: str = "wave_emit_test") -> ExperimentSpec:
    """A minimal in-memory ``ExperimentSpec`` — never loaded from a YAML file."""
    return ExperimentSpec(
        name=name,
        question="does the s3b emission hook work",
        version="0.1",
        workflow=Workflow(
            kind="agent_task", params={"model_pool": ["deepseek/deepseek-v4-flash"]}
        ),
        factors=[],
        design="factorial",
        stop=StopSpec(budget_usd=10.0, max_attempts=1),
    )


def _emit_result(
    *,
    spec_name: str = "wave_emit_test",
    ok: bool = True,
    awaiting: bool = False,
    n_phases: int = 8,
    cost_usd: float = 1.469705,
    run_id: str = "run-77f7b899f4f8",
    git_sha: str = "00d15dbf3",
) -> WorkflowRunResult:
    """A synthetic ``WorkflowRunResult`` shaped like the kb_finding_layer run's ledger.

    Exactly what ``scripts/run_workflow.py`` holds after ``run_workflow()`` returns (BEFORE the
    ledger write), which is what ``_control_terminal_write`` is actually handed. ``ok=False``
    yields the failed-run shape; ``awaiting=True`` the checkpoint-pause shape; ``n_phases=0``
    the nothing-ran/cancelled shape.
    """
    statuses = ["ok"] * n_phases
    if not ok:
        statuses[-1] = "failed"
    phases = [
        PhaseResult(
            phase=f"p{i}",
            kind="agent",
            status=statuses[i],
            model="deepseek/deepseek-v4-flash",
            commit_hash=f"c{i}",
            cost_usd=cost_usd / n_phases,
        )
        for i in range(n_phases)
    ]
    return WorkflowRunResult(
        spec_name=spec_name,
        spec_id=f"{spec_name}@0.1",
        model="deepseek/deepseek-v4-flash",
        workdir="/tmp/x",
        goal="build it",
        git_sha=git_sha,
        started_at=EMIT_NOW,
        ended_at=EMIT_NOW,
        run_id=run_id,
        parent_run_id="",
        family_id=run_id,
        awaiting=awaiting,
        phases=phases,
    )


class _EmitArgs:
    """The argparse namespace ``_control_terminal_write`` actually reads.

    ``no_fact_emit=True`` deliberately skips the fact producer — these tests prove the wave
    verdict path, and the fact path is exercised by ``test_fact_auto_emit.py``. The wave
    verdict is NOT behind that flag (default-on is asserted by these tests emitting while it
    is set).
    """

    workdir = "/tmp/x"
    model = "deepseek/deepseek-v4-flash"
    only_phase = None
    no_fact_emit = True


@pytest.fixture
def emission_env(rw, tmp_path, monkeypatch):
    """Redirect every durable path the terminal write touches, and stub the spec-index read."""
    monkeypatch.setenv("FINOPS_CONTROL_DB", str(tmp_path / "control" / "control.db"))
    monkeypatch.setattr("agentic_dynamics.core.paths.KB_ARTIFACT_DIR", tmp_path / "kb")
    monkeypatch.setattr(
        "agentic_dynamics.core.paths.REGISTRY_INDEX_PATH",
        tmp_path / "registry_index.jsonl",
    )
    monkeypatch.setattr(rw.si, "load_index_entries", lambda **kw: [])
    return tmp_path


def _mint_run(rw, spec) -> str:
    """Create the ``running`` run row the terminal write transitions out of."""
    run_id, db = rw._control_open_run(spec, _EmitArgs())
    if db is not None:
        db.close()
    return run_id


class _FakeRedis:
    """The minimal handle the publisher needs: a consumer-checkpoint hash."""

    def __init__(self):
        self._checkpoint: dict[str, str] = {}

    def hget(self, key, field):
        return self._checkpoint.get(field)

    def hset(self, key, field, value):
        self._checkpoint[field] = value


def _run_terminal_write(
    rw, emission_env, monkeypatch, spec, result, *, run_id, review_text=None
) -> tuple[_FakeRedis, list]:
    """Drive the real ``_control_terminal_write`` against the hermetic environment.

    Returns ``(fake_redis, published)`` — the fake stream handle and the list of pointer
    events the (stubbed) ``publish_event`` captured. ``review_text`` (when given) is written to
    ``<emission_env>/docs/reviews/<spec>_adversarial.md`` first, modelling an adversarial phase
    that already ran inside the workflow.
    """
    from agentic_dynamics.knowledge import knowledge_stream as real_ks

    fake_redis = _FakeRedis()
    published: list = []
    monkeypatch.setattr(real_ks, "connect", lambda *a, **kw: fake_redis)
    monkeypatch.setattr(real_ks, "publish_event", lambda r, e, **kw: published.append(e) or "1-0")
    if review_text is not None:
        doc = emission_env / "docs" / "reviews" / f"{spec.name}_adversarial.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(review_text, encoding="utf-8")
    rw._control_terminal_write(
        spec, _EmitArgs(), result, run_id=run_id, ledger_path=Path("/tmp/ledger.json")
    )
    return fake_redis, published


def _verdict_artifacts(emission_env) -> list[Path]:
    """The durable ``wave-verdict`` artifacts the publisher wrote under the redirected KB dir."""
    kb = emission_env / "kb"
    out = []
    for path in sorted(kb.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("extractor_version") == wv.EXTRACTOR_VERSION:
            out.append(path)
    return out


def _verdict_payload(path: Path) -> dict:
    return json.loads(json.loads(path.read_text(encoding="utf-8"))["text"])


def _outbox_state(emission_env, run_id) -> tuple:
    from agentic_dynamics.control.outbox import summarize

    db = ControlDB.open_read_only(emission_env / "control" / "control.db")
    try:
        summary = summarize(db, run_id=run_id)
        state = db.get_run(run_id).state
    finally:
        db.close()
    return state, summary


class TestTerminalWriteEmission:
    """s3b DONE_WHEN: the run-completion path emits the wave verdict — completed + failed."""

    def test_a_completed_run_emits_its_wave_verdict_with_the_measured_fields(
        self, rw, emission_env, monkeypatch
    ):
        """A synthetic succeeded run emits ONE wave-verdict record with the measured fields.

        The verdict is queued in the terminal write's atomic transaction and delivered
        artifact-first by the drain; ``no_fact_emit=True`` proves it is NOT behind the fact
        flag (default-on).
        """
        spec = _emit_spec()
        result = _emit_result()
        run_id = _mint_run(rw, spec)
        # The composition root stamps the control run id onto the result before the terminal
        # write (g1) — mirror it so the ledger's run_id is the run row's.
        result.run_id = run_id

        _run_terminal_write(rw, emission_env, monkeypatch, spec, result, run_id=run_id)

        artifacts = _verdict_artifacts(emission_env)
        assert len(artifacts) == 1
        payload = _verdict_payload(artifacts[0])
        assert payload["spec_name"] == "wave_emit_test"
        assert payload["run_id"] == run_id
        assert payload["verdict"] == "clean"  # no review doc → the run's own green disposition
        assert payload["cost"] == pytest.approx(1.469705)
        assert payload["phases_total"] == 8
        assert payload["merge_state"] == "promotable"  # the control-db terminal row, verbatim
        assert payload["actor"] == "run"
        assert payload["scope"] == wv.wave_verdict_acl_scope("wave_emit_test", result.model)
        assert "adversarial_findings_count" not in payload  # no review → never a fabricated 0
        assert "wave_emit_test" in payload["narrative"] and run_id in payload["narrative"]

        state, summary = _outbox_state(emission_env, run_id)
        assert state is RunState.PROMOTABLE
        assert summary.delivered == 1 and summary.pending == 0 and summary.dead == 0

    def test_a_failed_run_emits_its_failed_wave_verdict(
        self, rw, emission_env, monkeypatch
    ):
        """A failure is a verdict, not a silence: a failed run still emits — verdict ``not``."""
        spec = _emit_spec()
        result = _emit_result(ok=False)
        assert result.state == "failed"
        run_id = _mint_run(rw, spec)
        result.run_id = run_id

        _run_terminal_write(rw, emission_env, monkeypatch, spec, result, run_id=run_id)

        artifacts = _verdict_artifacts(emission_env)
        assert len(artifacts) == 1
        payload = _verdict_payload(artifacts[0])
        assert payload["run_id"] == run_id
        assert payload["verdict"] == "not"
        assert payload["merge_state"] == "failed"
        assert payload["phases_total"] == 8
        assert "adversarial_findings_count" not in payload
        assert payload["actor"] == "run"
        assert payload["scope"] == wv.wave_verdict_acl_scope("wave_emit_test", result.model)

        state, summary = _outbox_state(emission_env, run_id)
        assert state is RunState.FAILED
        assert summary.delivered == 1 and summary.pending == 0

    def test_a_review_doc_at_completion_flows_into_the_emitted_verdict(
        self, rw, emission_env, monkeypatch
    ):
        """When the run's adversarial phase already committed its doc, the verdict reads it.

        The emitted verdict carries the review's merge-ready signal and finding count — the
        emission reads the doc that exists at completion, exactly as the s3a type does.
        """
        spec = _emit_spec()
        result = _emit_result()
        review = """---
status: accepted
kind: adversarial_review
spec: wave_emit_test
---
# wave_emit_test — adversarial review

**Verdict: PASS (merge-ready).** The claim held under independent probe.

| # | Attack | Disposition | Reasoning |
|---|---|---|---|
| F1 | probe A | **RECORD** (accepted limitation) | corpus-sensitive |
| F2 | probe B | **RECORD** (accepted limitation) | forward-only |
"""
        run_id = _mint_run(rw, spec)

        _run_terminal_write(
            rw, emission_env, monkeypatch, spec, result, run_id=run_id, review_text=review
        )

        artifacts = _verdict_artifacts(emission_env)
        assert len(artifacts) == 1
        payload = _verdict_payload(artifacts[0])
        assert payload["verdict"] == "merge-ready"
        assert payload["adversarial_findings_count"] == 2
        assert payload["residuals"]  # the recorded limitations ride along
        assert payload["merge_state"] == "promotable"

    def test_an_awaiting_run_emits_no_wave_verdict(self, rw, emission_env, monkeypatch):
        """A designed checkpoint pause is not a completion — no premature (negative) verdict.

        The run's family continues; the verdict belongs to the run that finally terminates.
        """
        spec = _emit_spec()
        result = _emit_result(awaiting=True)
        assert result.state == "awaiting_approval"
        run_id = _mint_run(rw, spec)

        _run_terminal_write(rw, emission_env, monkeypatch, spec, result, run_id=run_id)

        assert _verdict_artifacts(emission_env) == []
        state, summary = _outbox_state(emission_env, run_id)
        assert state is RunState.AWAITING_APPROVAL
        assert summary.delivered == 0 and summary.pending == 0

    def test_a_cancelled_run_that_ran_nothing_emits_no_wave_verdict(
        self, rw, emission_env, monkeypatch
    ):
        """Nothing ran → nothing to judge: a zero-phase cancelled run emits no verdict."""
        spec = _emit_spec()
        result = _emit_result(n_phases=0)
        assert result.state == "cancelled"
        run_id = _mint_run(rw, spec)

        _run_terminal_write(rw, emission_env, monkeypatch, spec, result, run_id=run_id)

        assert _verdict_artifacts(emission_env) == []
        state, summary = _outbox_state(emission_env, run_id)
        assert state is RunState.CANCELLED
        assert summary.delivered == 0 and summary.pending == 0

    def test_a_wave_verdict_derivation_failure_never_fails_the_run(
        self, rw, emission_env, monkeypatch, capsys
    ):
        """Best-effort under the same ``_derived`` fence as the spec/fact producers.

        A raising verdict derivation costs THAT producer's event and nothing else: the run's
        terminal state is still recorded. The patch is local to the fresh module under test.
        """
        spec = _emit_spec()
        result = _emit_result()

        def boom(*a, **kw):
            raise RuntimeError("simulated wave-verdict derivation bug")

        monkeypatch.setattr(rw, "_wave_verdict_review_text", boom)
        run_id = _mint_run(rw, spec)
        _run_terminal_write(rw, emission_env, monkeypatch, spec, result, run_id=run_id)

        assert "warning: wave verdict derivation failed" in capsys.readouterr().err
        assert _verdict_artifacts(emission_env) == []
        state, summary = _outbox_state(emission_env, run_id)
        assert state is RunState.PROMOTABLE  # the state survived the producer failure
        assert summary.pending == 0  # the failed producer queued nothing

