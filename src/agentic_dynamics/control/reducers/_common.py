"""Shared, pure helpers for the CAP reducers.

Deliberately a *leaf* module: no I/O, no Redis, no store imports — only the primitives every
reducer needs to (a) encode a measured value into its canonical STRING form, (b) coerce an
evidence payload to a plain field dict, (c) compute the workflow-cell id that names a run's job
scope, and (d) compute the identity of one persisted run ARTIFACT (as opposed to the cell it
belongs to). Keeping these here (rather than re-declaring them in each reducer) means two
reducers can never drift on how a value serializes, how a cell is named, or how a run is
identified — any of which would silently re-key ``fact_id`` and break the byte-for-byte
idempotence gate, or worse, let two distinct runs collide on identity (the CAP I0-I3 repair's
load-bearing invariant).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

#: Fallback ``source_revision`` for a run JSON that carries no ``git_sha`` (e.g. a
#: ``--no-commit`` run). Pinned to the artifact kind rather than fabricating a commit — the same
#: posture as ``ledger_ingestion.REVISION_FALLBACK``.
REVISION_FALLBACK = "workflow-run/unrevisioned"


def encode_value(value: Any, value_type: str) -> str:
    """Encode one measured value into its canonical STRING form (design §3.1).

    Deterministic by construction: the same value always renders to the same string, which is
    what keeps ``fact_id`` (via the hashed payload) reproducible across re-derivations. Mirrors
    the encoding ``spec_status.py`` uses, factored here for the I2 reducers.
    """
    if value_type == "bool":
        return "true" if value else "false"
    if value_type == "int":
        return str(int(value))
    if value_type in ("float", "usd"):
        return str(value)  # str(float) is the shortest round-trip form; deterministic
    if value_type == "enum-list":
        return ",".join(str(v) for v in value)
    return str(value)  # str | enum | tokens | timestamp


def cell_id(spec_name: str, model: str) -> str:
    """Return the workflow-cell id for a run: ``wf_<spec>_<model>``.

    Mirrors ``workflow_runner._cell_id`` (``workflow_runner.py:257``) verbatim, re-declared here
    (rather than imported) so a reducer stays import-light — it must not pull the whole
    execution runtime just to name a cell. This is the JOB scope id (§10.1's "workflow cell").
    """
    slug = "".join(ch if ch.isalnum() else "_" for ch in f"{spec_name}_{model}")
    return f"wf_{slug.lower().strip('_')}"


def run_artifact_id(run: dict[str, Any]) -> str:
    """Return the deterministic identity of ONE persisted workflow-run artifact.

    Content-addressed: sha256 over the run's own recorded fields (spec_name, model, git_sha,
    started_at, ended_at, per-phase session ids, ...), rendered as canonical (sorted-key) JSON.
    This is the identity tuple the CAP I0-I3 repair introduces at the ``EvidenceItem`` boundary
    (design invariant): re-deriving facts from the SAME artifact twice hashes the same bytes and
    yields the same id (byte-for-byte stability), while two DISTINCT artifacts — even ones that
    happen to share ``spec_name``/``model``/phase names/values — get different ids as soon as any
    of their own recorded fields differ, which in practice is always true (every run records its
    own ``started_at`` at minimum).

    Deliberately never touches ``ReducerInput.now`` (the injected clock) or the wall clock or a
    random id: the artifact IS its own identity, computed purely from what it already recorded.
    """
    canonical = json.dumps(run, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_recency_key(run: dict[str, Any]) -> str:
    """Return the run's own recorded recency token (``ended_at`` else ``started_at`` else "").

    Used to order runs deterministically by when THEY say they happened — never by wall clock —
    so a batch of facts derived from several runs of one cell can be processed oldest-first and
    have the most-recently-recorded run's value win (job facts are current-per-cell summaries;
    see ``job_facts.py``).
    """
    return str(run.get("ended_at") or run.get("started_at") or "")


def as_dict(payload: Any) -> dict[str, Any] | None:
    """Coerce one evidence payload into a plain field dict (accepts a dict or a
    ``to_dict()``-carrying object such as ``WorkflowRunResult``/``PhaseResult``)."""
    if isinstance(payload, dict):
        return payload
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        coerced = to_dict()
        return coerced if isinstance(coerced, dict) else None
    return None
