"""Campaign-evidence producer — scored proposal/outcome pairs as [M] findings.

THE EVIDENCE-FOR-INTELLIGENCE SEAM (cap_2a review, boundary wiring): a shadow/control campaign
scores each cell's proposal against its realized outcome (hit/miss, risk, critical counts, ...).
That scored evidence is intelligence — "does the verification gate's proposal predict the
realized outcome" — and it belongs in the canonical registry as queryable [M] findings, not in
archived score JSONs. This producer ingests one campaign score JSON (schema ``cap_2a_score/v1``):

* one finding record PER SCORED CELL — text mirrors the phase-finding one-liner style:
  ``<campaign> cell <cell_id> -> proposal <action>/<depth> realized <outcome> hit <bool>,
  risk <r>, new_critical <n>`` — authority MEASURED (the outcome is test-runner/ledger-measured;
  hit is computed from the fixed scoring semantics), evidence_class ``[M]``;
* one AGGREGATE finding record per campaign — hit-rate, n, Wilson interval, risk_mint_rate —
  authority MEASURED, evidence_class ``[M]``.

Scope: ``repository_id = acl_scope = logical_locator = "cap_2a:<campaign>"`` (the campaign is
the evidence's unit, queryable alongside the corpus). Idempotence: ``knowledge_id`` folds
text + revision + scope + extractor version (``campaign-evidence/v1``), so re-ingesting the
same score JSON yields the same ids. The revision is the score JSON's ``source_revision``.

Pipe: ``build_record_from_parts`` -> ``record_to_artifact`` -> ``record_to_event`` ->
``publish_event`` (same as kb_produce_facts). Run with a kb worker draining the stream
(``python scripts/kb_worker.py --group kb-registry-v1 --once``) to compact into
registry_index.jsonl.

Invocation:
    python3 scripts/kb_produce_campaign_evidence.py --score <path> [--campaign <name>] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from agentic_dynamics.knowledge import knowledge_ingestion as ki  # noqa: E402
from agentic_dynamics.knowledge import knowledge_stream as ks  # noqa: E402
from agentic_dynamics.knowledge.knowledge_ingestion import Authority  # noqa: E402

EXTRACTOR_VERSION = "campaign-evidence/v2"
REDIS_HOST = os.environ.get("FINOPS_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.environ.get("FINOPS_REDIS_PORT", "6380"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cell_record(cell: dict, *, campaign: str, revision: str, now: str) -> ki.KnowledgeRecord:
    payload = {
        "campaign": campaign,
        "cell_id": cell.get("cell_id"),
        "proposal_id": cell.get("proposal_id"),
        "action": cell.get("proposal_action"),
        "depth": cell.get("proposal_depth"),
        "proposal_scope": cell.get("proposal_scope"),
        "realized_outcome": cell.get("realized_outcome"),
        "realized_depth": cell.get("realized_depth"),
        "realized_symbol_set": cell.get("realized_symbol_set"),
        "hit": cell.get("hit"),
        "code_change_risk": cell.get("code_change_risk"),
        "new_sonar_critical_count": cell.get("new_sonar_critical_count"),
        "new_lsp_error_count": cell.get("new_lsp_error_count"),
        "graph_status": cell.get("graph_status"),
        "sonar_status": cell.get("sonar_status"),
        "lsp_status": cell.get("lsp_status"),
        "spec_id": cell.get("spec_id"),
        "baseline_revision": cell.get("baseline_revision"),
        "analyzed_revision": cell.get("analyzed_revision"),
    }
    one_liner = (
        f"{campaign} cell {cell.get('cell_id')} -> proposal {cell.get('proposal_action')}/"
        f"{cell.get('proposal_depth')} realized {cell.get('realized_outcome')} "
        f"hit {cell.get('hit')}, risk {cell.get('code_change_risk')}, "
        f"new_critical {cell.get('new_sonar_critical_count')}"
    )
    # The structured payload rides in ``text`` (the free-form canonical container) as a JSON
    # suffix; the record's own fields map the known vocabulary (outcome_id = the cell, commit_sha
    # = the analyzed revision). ``content_hash`` covers text, so the payload is provenance.
    text = one_liner + " :: " + json.dumps(payload, sort_keys=True)
    return ki.build_record_from_parts(
        # source_type="report" (measured artifact) — NOT "finding": the canonical finding table
        # resolves rows against the perturbation-experiment payload schema ({"runs":[...]} with
        # workdir locators), which campaign scoring rows do not satisfy; report rows carry no
        # canonical-table payload obligation, and report is a MEASURED [M] source_type.
        source_type="report",
        source_uri=f"file://experiments/results/{campaign}/score.json",
        logical_locator=f"cap_2a:{campaign}:cell:{cell.get('cell_id')}",
        repository_id=f"cap_2a:{campaign}",
        revision=revision,
        authority=Authority.MEASURED,
        evidence_class="[M]",
        text=text,
        extra_fields={
            "extractor_version": EXTRACTOR_VERSION,
            "acl_scope": f"cap_2a:{campaign}",
            "worktree_id": f"cap_2a:{campaign}",
            "outcome_id": str(cell.get("cell_id") or ""),
            "commit_sha": str(cell.get("analyzed_revision") or ""),
        },
        now=now,
    )


def _aggregate_record(
    agg: dict, *, campaign: str, revision: str, now: str
) -> ki.KnowledgeRecord:
    ci = agg.get("wilson_95_ci") or []
    payload = {
        "campaign": campaign,
        "aggregate": True,
        "n_scored": agg.get("n_scored"),
        "n_hits": agg.get("n_hits"),
        "n_unknown_outcome": agg.get("n_unknown_outcome"),
        "n_invalid_join": agg.get("n_invalid_join"),
        "n_not_run": agg.get("n_not_run"),
        "wilson_95_ci": ci,
        "risk_mint_rate": agg.get("risk_mint_rate"),
    }
    text = (
        f"{campaign} scored -> hit-rate {agg.get('n_hits')}/{agg.get('n_scored')} "
        f"(wilson [{ci[0] if ci else '?'}, {ci[1] if len(ci) > 1 else '?'}]), "
        f"risk_mint_rate {agg.get('risk_mint_rate')}, "
        f"unknown {agg.get('n_unknown_outcome')} invalid {agg.get('n_invalid_join')} "
        f"not_run {agg.get('n_not_run')}"
    ) + " :: " + json.dumps(payload, sort_keys=True)
    return ki.build_record_from_parts(
        source_type="report",
        source_uri=f"file://experiments/results/{campaign}/score.json",
        logical_locator=f"cap_2a:{campaign}:aggregate",
        repository_id=f"cap_2a:{campaign}",
        revision=revision,
        authority=Authority.MEASURED,
        evidence_class="[M]",
        text=text,
        extra_fields={
            "extractor_version": EXTRACTOR_VERSION,
            "acl_scope": f"cap_2a:{campaign}",
            "worktree_id": f"cap_2a:{campaign}",
            "outcome_id": "aggregate",
        },
        now=now,
    )


def derive_campaign_records(score: dict, *, campaign: str) -> list[ki.KnowledgeRecord]:
    """One [M] finding per scored cell + one aggregate finding, from a cap_2a_score/v1 JSON."""
    revision = str(score.get("source_revision") or score.get("spec_version") or "")
    now = _now()
    records: list[ki.KnowledgeRecord] = []
    for cell in score.get("cells") or []:
        records.append(_cell_record(cell, campaign=campaign, revision=revision, now=now))
    agg = score.get("aggregates") or {}
    if agg:
        records.append(_aggregate_record(agg, campaign=campaign, revision=revision, now=now))
    return records


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--score", required=True, help="path to a cap_2a_score/v1 JSON")
    ap.add_argument("--campaign", default="", help="campaign name (default: from file name)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    score = json.loads(Path(args.score).read_text())
    campaign = args.campaign or Path(args.score).stem.split("_score_")[0]
    records = derive_campaign_records(score, campaign=campaign)

    if args.dry_run:
        for record in records:
            print(f"  {record.knowledge_id[:12]}  [finding/upsert]  {record.logical_locator}  {record.text}")
        print(f"dry-run: {len(records)} record(s)")
        return

    os.environ["FINOPS_KB_WRITE"] = "1"
    r = ks.connect(host=REDIS_HOST, port=REDIS_PORT)
    from agentic_dynamics.core.paths import KB_ARTIFACT_DIR, REGISTRY_INDEX_PATH

    for record in records:
        # Mirrors kb_produce_facts.emit_records (the F2 pattern): the durable artifact is
        # written BEFORE the event lands (the consumer verifies the bytes the event hashes —
        # a missing artifact file dead-letters the event), the event is published for the
        # other consumers (chroma/neo4j/ledger), the id is checkpointed, and the registry row
        # is materialized at EMIT time so the evidence is registry-visible immediately — no
        # dependency on a live kb-registry consumer. A later consumer pass appends
        # byte-identical duplicate lines; generate_manifest.py's compaction folds them.
        artifact = ki.record_to_artifact(record)
        KB_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        (KB_ARTIFACT_DIR / f"{record.knowledge_id}.json").write_bytes(artifact)
        event = ki.record_to_event(record)
        ks.publish_event(r, event, source_type=record.source_type)
        r.hset(ks.CHECKPOINT_KEY, record.knowledge_id, record.indexed_at)
        line = {
            "knowledge_id": record.knowledge_id,
            "entity_id": record.entity_id,
            "source_type": record.source_type,
            "logical_locator": record.logical_locator,
            "source_uri": record.source_uri,
            "lifecycle_state": "current",
            "observed_at": record.observed_at,
            "indexed_at": record.indexed_at,
            "supersedes": record.supersedes,
            "causes": record.causes,
            "reason": "",
        }
        REGISTRY_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(REGISTRY_INDEX_PATH, "a") as f:
            f.write(json.dumps(line) + "\n")
        print(f"emitted {record.knowledge_id[:12]} [{record.source_type}] {record.text.split(' :: ')[0]}")
    print(f"emitted={len(records)} (artifact + event + registry row)")


if __name__ == "__main__":
    main()
