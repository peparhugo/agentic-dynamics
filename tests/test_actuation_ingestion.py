"""Tests for actuation ingestion (actuation_ingestion).

Covers the POLICY/[P] provenance, the required-``causes`` construction-time check
(design §5a, ahead of the transport-level lineage gate in ``knowledge_stream.publish_event``),
identity derivation ("one identity per candidate, not per session" — design §3), the
reused artifact/event contract, and — the plan's own explicit CI-enforced invariant
(``docs/canonical_state_r2_plan.md`` step 6) — that this producer's ONLY call site is the
Control Room's steer/interrupt handlers (``apps/control_room/server.py``); ``scripts/supervise.py`` and
``src/instrument/workflow_runner.py`` stay call-site-free.
"""

import ast
import hashlib
from pathlib import Path

import pytest

from agentic_dynamics.control import actuation_ingestion as ai
from agentic_dynamics.knowledge.knowledge import Authority
from agentic_dynamics.knowledge.knowledge_ingestion import record_to_artifact

pytestmark = pytest.mark.fast

REPO_ROOT = Path(__file__).resolve().parent.parent


def _candidate(**overrides) -> dict:
    base = {
        "actuation_kind": "steer",
        "target_session_id": "sess_abc123",
        "target_cell_id": "wf_task_manager_api_1",
        "requested_action": {"note": "nudge back toward the spec"},
        "requested_by": "supervisor",
        "causes": "obs_knowledge_id_0001",
    }
    base.update(overrides)
    return base


# ── Extractor contract constants ────────────────────────────────


def test_extractor_constants():
    assert ai.EXTRACTOR_VERSION == "actuation/v1"
    assert ai.SOURCE_TYPE == "actuation"
    assert ai.ACL_SCOPE == "public"
    assert {
        "steer", "interrupt", "escalate", "retry", "budget", "deadline",
    } == ai.ACTUATION_KINDS


# ── Provenance ───────────────────────────────────────────────────


def test_actuation_authority_is_policy_and_p():
    record = ai.derive_actuation_record(_candidate())
    assert record.authority is Authority.POLICY
    assert record.evidence_class == "[P]"


def test_causes_is_set_on_the_record():
    record = ai.derive_actuation_record(_candidate())
    assert record.causes == "obs_knowledge_id_0001"


# ── Required `causes` — construction-time check (design §5a) ────


def test_derive_actuation_record_requires_causes():
    with pytest.raises(ValueError):
        ai.derive_actuation_record(_candidate(causes=""))


def test_derive_actuation_record_requires_causes_key_present():
    candidate = _candidate()
    del candidate["causes"]
    with pytest.raises(ValueError):
        ai.derive_actuation_record(candidate)


# ── Identity: one per candidate, not per session ─────────────────


def test_repeated_candidates_against_the_same_session_are_independent_facts():
    a = ai.derive_actuation_record(_candidate())
    b = ai.derive_actuation_record(_candidate())
    # Distinct occurred_at (the two calls happen at different wall-clock instants) means
    # distinct actuation_id, hence distinct entity_id — never versions of the same entity.
    assert a.entity_id != b.entity_id


def test_actuation_id_folds_in_target_session_and_causes():
    a = ai.derive_actuation_record(_candidate(target_session_id="sess_1"))
    b = ai.derive_actuation_record(_candidate(target_session_id="sess_2"))
    assert a.entity_id != b.entity_id


# ── Body rendering ───────────────────────────────────────────────


def test_text_is_the_json_body_with_all_five_fields():
    import json

    record = ai.derive_actuation_record(_candidate())
    body = json.loads(record.text)
    assert body == {
        "actuation_kind": "steer",
        "target_session_id": "sess_abc123",
        "target_cell_id": "wf_task_manager_api_1",
        "requested_action": {"note": "nudge back toward the spec"},
        "requested_by": "supervisor",
    }


def test_real_actuation_record_does_not_carry_applied_marker():
    # CAP shadow-fact disposition (p2): the `applied: false` marker is stamped ONLY on shadow
    # decisions, inside record_shadow_decision (control/rules.py). A REAL actuation record —
    # constructed here with no arming, exactly as the disposition spec's "if one can be
    # constructed without arming" clause asks — must NOT carry the field: it is a genuine,
    # executed-actuation-shaped record, distinguishable from a proposed-never-executed shadow
    # decision precisely by the marker's ABSENCE. This is the contrast side of
    # test_shadow_decision_carries_applied_false_marker (test_context_plane_seam.py).
    import json

    record = ai.derive_actuation_record(_candidate())
    body = json.loads(record.text)
    params = (body.get("requested_action") or {}).get("parameters") or {}
    assert "applied" not in params, (
        "a real actuation record must not carry the shadow-only `applied` marker"
    )


# ── Reused artifact/event contract ──────────────────────────────


def test_content_hash_equals_sha256_of_record_to_artifact():
    record = ai.derive_actuation_record(_candidate())
    assert record.content_hash == hashlib.sha256(record_to_artifact(record)).hexdigest()


# ── CI-enforced invariant: zero call sites today ─────────────────


def _calls_derive_actuation_record(path: Path) -> bool:
    """Return True if ``path`` contains a syntactic call/reference to
    ``derive_actuation_record`` (as a bare name, an attribute access, or an import)."""
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "derive_actuation_record":
            return True
        if isinstance(node, ast.Attribute) and node.attr == "derive_actuation_record":
            return True
        if isinstance(node, (ast.ImportFrom, ast.Import)):
            for alias in node.names:
                if alias.name == "derive_actuation_record":
                    return True
    return False


def test_no_call_sites_construct_actuation_records():
    # design §5b / §13: the ONLY legitimate actuation call site today is the Control
    # Room's steer/interrupt handlers (apps/control_room/server.py: _emit_actuation_record, wired
    # per review §5.4 — the human-gated "why did the system act" audit trail). The
    # supervisor and workflow runner must stay call-site-free: a control rule for
    # actuation in a compiled ExperimentSpec is still the prerequisite for any OTHER
    # caller, so this test keeps guarding every non-Control-Room module.
    guarded_files = [
        REPO_ROOT / "scripts" / "supervise.py",
        REPO_ROOT / "src" / "instrument" / "workflow_runner.py",
    ]
    offenders = [
        str(f.relative_to(REPO_ROOT))
        for f in guarded_files
        if f.exists() and _calls_derive_actuation_record(f)
    ]
    assert offenders == [], f"unexpected actuation call site(s): {offenders}"
