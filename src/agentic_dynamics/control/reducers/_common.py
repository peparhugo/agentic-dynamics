"""Shared, pure helpers for the CAP reducers.

Deliberately a *leaf* module: no I/O, no Redis, no store imports — only the primitives every
reducer needs to (a) encode a measured value into its canonical STRING form, (b) coerce an
evidence payload to a plain field dict, and (c) compute the workflow-cell id that names a run's
job scope. Keeping these here (rather than re-declaring them in each reducer) means two reducers
can never drift on how a value serializes or how a cell is named — which would silently re-key
``fact_id`` and break the byte-for-byte idempotence gate.
"""

from __future__ import annotations

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
