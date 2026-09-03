"""Tests for the finding-layer leg projection (kb_finding_layer k6 — the witness).

``scripts/kb_project_findings.py`` materializes durable finding artifacts into the retrieval
legs via the kb_worker handler bodies. These tests cover the pure selection/reconstruction
logic and the projection dispatch with a stubbed handler factory — never a live store. The
witness's real leg write is exercised in the k6 phase itself (docs/fleet/10_...k6_witness.md).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "kb_project_findings", ROOT / "scripts" / "kb_project_findings.py"
)
assert SPEC is not None and SPEC.loader is not None
kpf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kpf)

from agentic_dynamics.knowledge.knowledge import Authority  # noqa: E402
from agentic_dynamics.knowledge.record_factory import build_record  # noqa: E402


def _make_finding(root: Path, *, scope: str, extractor: str, text: str) -> str:
    """Write one finding artifact into ``root/experiments/results/kb``; return its id."""
    record = build_record(
        source_type="finding",
        source_uri="file://experiments/results/kb/<id>.json",
        logical_locator=scope,
        repository_id=scope,
        revision="abc1234",
        authority=Authority.MEASURED,
        evidence_class="[M]",
        text=text,
        extra_fields={
            "extractor_version": extractor,
            "acl_scope": scope,
            "outcome_id": "p1",
            "test_executed_success": True,
        },
    )
    from agentic_dynamics.knowledge.record_factory import record_to_artifact

    kb = root / "experiments" / "results" / "kb"
    kb.mkdir(parents=True, exist_ok=True)
    (kb / f"{record.knowledge_id}.json").write_bytes(record_to_artifact(record))
    return record.knowledge_id


def test_discover_selects_only_finding_artifacts(tmp_path):
    """(a) discovery keeps only source_type=finding and honours the extractor/only filters."""
    backfill_id = _make_finding(
        tmp_path, scope="wave:control_db_evidence", extractor="wave-backfill/v1",
        text="wave control_db_evidence -> verdict not, findings 5 :: residuals",
    )
    phase_id = _make_finding(
        tmp_path, scope="self-wt_wave4", extractor="phase-finding/v1",
        text="Close the knowledge-base finding-layer gap phase p1 -> test_executed_success True",
    )
    # A non-finding artifact (code) must never be selected.
    (tmp_path / "experiments" / "results" / "kb" / "zzz_not_finding.json").write_text(
        json.dumps({"source_type": "code", "text": "def f(): pass"})
    )

    all_findings = kpf.select_records(tmp_path)
    assert {r.knowledge_id for r in all_findings} == {backfill_id, phase_id}

    only_backfill = kpf.select_records(tmp_path, extractors={"wave-backfill/v1"})
    assert [r.knowledge_id for r in only_backfill] == [backfill_id]

    only_phase = kpf.select_records(tmp_path, only={phase_id[:12]})
    assert [r.knowledge_id for r in only_phase] == [phase_id]

    limited = kpf.select_records(tmp_path, limit=1)
    assert len(limited) == 1


def test_load_record_reattaches_derived_identity(tmp_path):
    """(b) the durable artifact blanks ids; load_record reattaches them deterministically.

    ``knowledge_id`` is the filename and ``content_hash`` re-derives as sha256 of the exact
    artifact bytes — the same values the consumer's verification would compute, so the
    projection is byte-consistent with the event contract.
    """
    kid = _make_finding(
        tmp_path, scope="wave:control_db_evidence", extractor="wave-backfill/v1",
        text="wave control_db_evidence -> verdict not, findings 5",
    )
    raw = (tmp_path / "experiments" / "results" / "kb" / f"{kid}.json").read_bytes()
    # The artifact itself carries a blanked knowledge_id (the pointer contract).
    assert json.loads(raw)["knowledge_id"] == ""

    record = kpf.load_record(tmp_path / "experiments" / "results" / "kb" / f"{kid}.json")
    assert record.knowledge_id == kid
    assert record.content_hash == kpf._sha256_bytes(raw)
    assert record.source_type == "finding"
    assert record.text.startswith("wave control_db_evidence")


def test_project_dispatches_to_handler_bodies_and_skips_registered(tmp_path):
    """(c+d) project() calls the per-leg handler per record; registry skips registered ids.

    The handler factory is stubbed (the real kb_worker bodies write live stores — exercised in
    the witness phase), so this asserts the DISPATCH contract: every requested leg receives
    every record as an upsert, and a record already present in ``registry_index.jsonl`` is
    skipped for the registry leg (rerun-safe no-op) while still projected to chroma/neo4j.
    """
    kid_a = _make_finding(
        tmp_path, scope="wave:control_db_evidence", extractor="wave-backfill/v1",
        text="wave control_db_evidence -> verdict not",
    )
    kid_b = _make_finding(
        tmp_path, scope="self-wt_wave4", extractor="phase-finding/v1",
        text="Close the knowledge-base finding-layer gap phase p1",
    )
    # kid_a is already registered (an emit-time row, the k2 pattern).
    reg = tmp_path / "experiments" / "results" / "registry_index.jsonl"
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text(json.dumps({"knowledge_id": kid_a, "source_type": "finding"}) + "\n")

    calls: dict[str, list[str]] = {"kb-chroma-v1": [], "kb-neo4j-v1": [], "kb-registry-v1": []}

    def factory(group, r):
        # The projection passes the kb_worker CONSUMER-GROUP name (the real handler bodies);
        # the stub records under the group so the dispatch contract is asserted verbatim.
        def handler(record, *, operation="upsert", reason=""):
            calls[group].append(record.knowledge_id)

        return handler

    records = kpf.select_records(tmp_path)
    counts = kpf.project(
        records,
        legs=("chroma", "neo4j", "registry"),
        root=tmp_path,
        handler_factory=factory,
    )
    assert counts == {"chroma": 2, "neo4j": 2, "registry": 1}
    # Registry leg: only the unregistered record (kid_b) was appended — kid_a was a no-op.
    assert sorted(calls["kb-registry-v1"]) == [kid_b]
    # Chroma/neo4j project every record (idempotent upserts).
    assert sorted(calls["kb-chroma-v1"]) == sorted([kid_a, kid_b])
    assert sorted(calls["kb-neo4j-v1"]) == sorted([kid_a, kid_b])
