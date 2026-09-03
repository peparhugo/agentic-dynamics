"""The measured scoreboard aggregation for the self-knowledge layer (loop 2).

Phase ``s5a_scoreboard_aggregation`` of the ``self_knowledge_layer`` workflow (design
``docs/designs/proposed/self_knowledge_layer.md``): the frequentist base of the machine's
game against itself. Every wave that completes emits its s3a wave-verdict record
(``knowledge/wave_verdict_ingestion.py`` — the "what happened and why" at run completion);
this module aggregates THOSE records into the scoreboard's measured rows — waves completed,
merge rate, adversarial-finding rate, cost per wave (mean/median), time-to-merge, phases per
wave, and the per-model split. **The rows are recomputed from the s3 records, never
hand-written totals**: the durable scoreboard document is only ever produced by re-aggregating
the ``wave-verdict/v1`` records (the ``agentic-dynamics scoreboard --recompute`` command), so
a total that does not trace to a record cannot exist.

Actor + scope follow the design's actor-layering table: the PRODUCER is the AIO (this is the
command that renders the machine's own record) and the aggregation lives at the org root
(``org:<repository_id>`` — the row "Scoreboard | AIO | org:repo (aggregate)"), readable by the
controller, the AIO, and the supervisor, never by cell agents. The s3 wave-verdict records it
consumes live in their own ``workload:<spec>/job:<cell>`` scopes (see
:func:`wave_verdict_ingestion.wave_verdict_acl_scope`); an org-root read resolves them, a
cell-scoped retrieval never does.

**Input.** The aggregation reads the durable wave-verdict records the s3b emission writes —
the ``*.json`` artifacts under the KB artifact dir classified by the ``wave-verdict/v1``
extractor (the same direct-read seam the session/decision/belief reads use: never the registry
projection, which requires a live consumer), or a records dir of bare verdict payloads. Each
record normalizes to ONE wave row:

* the s3a content fields (``spec_name``/``run_id``/``verdict``/``cost``/``phases_total``/
  ``merge_state``/``adversarial_findings_count`` when a review doc existed);
* ``model`` — resolved deterministically from the record's OWN ``scope`` job cell: the cell id
  is ``wf_<slug(spec)>_<slug(model)>`` (``wave_verdict_ingestion.job_cell_id``) and the
  record carries its ``spec_name`` verbatim, so ``slug(model)`` is the exact suffix after
  ``slug(spec_name) + "_"``; the slug is canonicalized against the corpus model vocabulary
  (:data:`MODEL_CATALOG`) when it matches. A wave whose scope yields no canonical model is
  excluded from the per-model split and reported in coverage — never bucketed under a guessed
  id;
* the two wave instants the timing row consumes (``started_at`` — the wave's start — and
  ``merged_at`` — when it reached its permanence state) — read from the record's payload
  when a producer records them.

**Measured-or-absent (never fabricated).** A row with no backing field is absent, not zero:
an empty record set yields an empty-but-valid scoreboard (``waves_completed: 0`` and no
rate/mean/median — a fabricated ``0.0`` merge rate on no waves would read as a measured
clean record); a merged wave whose record carries no timing contributes nothing to the
time-to-merge row, and the coverage block names the gap (``merged_with_timing`` of
``merged``). This is the same measured-not-estimated rule ``aggregate_workflow_metrics.py``
applies to the workflow ledgers.

Recorded limitations (fix-or-record, reported in the durable document's ``coverage``):

1. **The timing row measures what records carry.** Today's s3a emission derives the verdict
   from the run ledger + control row but does not write the wave's start/merge instants into
   the payload (s3a's content shape is pinned by its own phase; extending it is out of this
   phase's fence). The aggregation therefore computes time-to-merge only over merged waves
   whose records carry ``started_at`` + ``merged_at``, and reports the coverage. The row's
   arithmetic is proven over the fixture; real records light it up once an emission writes the
   instants.
2. **``merge_state`` is the state at emission.** A green run emits with the control state
   ``promotable`` (phases passing authorise a promotion, they do not ARE one); the merged
   standing of a wave that later reached permanence is recorded when its verdict is
   re-derived against the advanced control row (the s3a version chain). Until then the merge
   rate counts the waves whose record already reads ``merged``/``published``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_dynamics.core.constants import MODEL_LABELS
from agentic_dynamics.knowledge import wave_verdict_ingestion as wv
from agentic_dynamics.knowledge.knowledge_ingestion import REPOSITORY_ID
from agentic_dynamics.knowledge.session_ingestion import aio_acl_scope

# ── Extractor contract constants ────────────────────────────────

#: The source_type the aggregated records carry (the s3a family). The scoreboard adds no new
#: source type — it is a read + aggregation over the wave-verdict records that already exist.
SOURCE_TYPE = wv.SOURCE_TYPE

#: The extractor generation the read seam classifies on. Delegated from the s3a type so the two
#: phases can never drift apart on the family discriminator.
EXTRACTOR_VERSION = wv.EXTRACTOR_VERSION

#: The producer/actor of the aggregation: the AIO renders the machine's own scoreboard at the
#: org root (the design's actor-layering table: ``aio | org:repo (aggregate)``).
ACTOR = "aio"

#: The control states that count as "the wave reached permanence" for the merge-rate row.
#: ``merged`` is the squash-commit onto main; ``published`` the released state beyond it. A
#: ``promotable`` run is a completed wave that authorises a promotion — it has not merged.
MERGE_STATES = frozenset({"merged", "published"})

#: The wave-verdict vocabulary the aggregation reports over (the s3a/corpus words).
VERDICTS = wv.VERDICTS

#: The optional payload keys a record may carry for the timing row — ``started_at`` (the wave's
#: start instant) and ``merged_at`` (when the wave reached its permanence state). Not part of
#: the pinned s3a content shape (see the module docstring's recorded limitations); the
#: aggregation reads them when present and reports coverage when absent.
TIMING_FIELDS = ("started_at", "merged_at")


# ── Model resolution (deterministic, from the record's own scope) ──


def _slug(text: str) -> str:
    """The job-cell slugging convention (``wave_verdict_ingestion.job_cell_id``'s inner map)."""
    return "".join(ch if ch.isalnum() else "_" for ch in text).lower().strip("_")


def _model_catalog() -> dict[str, str]:
    """The slug -> canonical model id map, derived from the corpus model vocabulary.

    ``MODEL_LABELS`` keys ARE the canonical model ids the corpus records (the map is the
    model-id -> display-label vocabulary); the slug of each canonical id is what a wave-verdict
    record's job cell embeds, so this map is the deterministic inverse. Derived once per call so
    the module stays import-light and the vocabulary never goes stale in a constant.
    """
    return {_slug(model): model for model in MODEL_LABELS if model}


#: The reverse model vocabulary: ``slug(model)`` -> canonical model id (see :func:`_model_catalog`).
MODEL_CATALOG: dict[str, str] = _model_catalog()


def decode_model_slug(slug: str) -> str:
    """Return the canonical model id a job-cell model slug stands for, or ``""`` when unknown.

    A record's job cell embeds ``slug(model)`` (lossy by construction — ``/`` and ``-`` both
    become ``_``), so the scoreboard can never rebuild an arbitrary model string from the slug
    alone. It CAN resolve the slug against the corpus's own model vocabulary, which is exactly
    the set of models the corpus records: a slug that matches a canonical model's slug decodes
    to that model; a slug outside the vocabulary stays unresolved (``""``), and the wave is
    excluded from the per-model split (reported in coverage) — never a guessed id.
    """
    return MODEL_CATALOG.get(slug, "")


def model_from_payload(payload: dict[str, Any]) -> tuple[str, bool]:
    """Resolve the run's model from a wave-verdict payload: ``(model_id, resolved)``.

    The model is not a content field of the pinned s3a payload; it IS encoded in the payload's
    own ``scope`` — ``workload:<spec>/job:wf_<slug(spec)>_<slug(model)>`` — and ``slug`` is a
    char-wise map, so ``slug(spec + "_" + model) == slug(spec) + "_" + slug(model)``. Given the
    record's own ``spec_name`` (verbatim on the payload), ``slug(model)`` is therefore the exact
    suffix of the job cell after ``slug(spec_name) + "_"``. An explicit payload ``model`` key
    wins when present (a future emission may add it); otherwise the scope decode decides.

    Returns ``("", False)`` when no model is resolvable — the wave then counts in the totals but
    is excluded from the per-model split (its count is reported in coverage), never bucketed
    under a guessed model.
    """
    explicit = str(payload.get("model") or "").strip()
    if explicit:
        return explicit, True
    spec_name = str(payload.get("spec_name") or "").strip()
    scope = str(payload.get("scope") or "").strip()
    if not spec_name or not scope:
        return "", False
    marker = "job:"
    if marker not in scope:
        return "", False
    cell = scope.split(marker, 1)[1].strip()
    prefix = f"wf_{_slug(spec_name)}_"
    if not cell.startswith(prefix):
        return "", False
    slug = cell[len(prefix) :]
    if not slug:
        return "", False
    canonical = decode_model_slug(slug)
    if canonical:
        return canonical, True
    return slug, False


# ── Small deterministic helpers (measured-or-absent arithmetic) ──


def _is_number(value: Any) -> bool:
    """True for a real number (never a bool — a bool is not a measured quantity here)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_timestamp(text: Any) -> datetime | None:
    """Parse any ISO-8601 shape a record carries into an aware UTC datetime, or None.

    Mirrors ``aggregate_workflow_metrics.parse_timestamp``'s tolerance: ``...Z`` and
    ``...+00:00`` both occur and cannot be compared as strings; a naive instant is read as UTC.
    """
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _mean(values: list[float]) -> float | None:
    """The arithmetic mean of ``values``, or None when empty (an empty mean is not 0.0)."""
    if not values:
        return None
    return sum(values) / len(values)


def _median(values: list[float]) -> float | None:
    """The median of ``values``, or None when empty (an empty median is not 0.0)."""
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _rounded(value: float | None, digits: int = 6) -> float | None:
    """Round a computed figure (``None`` passes through untouched)."""
    return round(value, digits) if value is not None else None


# ── Wave-row normalization ──────────────────────────────────────


def normalize_wave(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize ONE wave-verdict payload into the scoreboard's measured wave row.

    The row keeps every content field the record carries (a missing ``adversarial_findings_count``
    stays absent — a wave without an adversarial review never reads as a zero-finding review),
    adds the resolved model (with its ``resolved`` flag), and computes the wave's time-to-merge
    in hours when it is a merged/published wave AND the record carries both timing instants
    (``started_at`` + ``merged_at``, parseable, ``merged_at`` after ``started_at``); otherwise
    ``time_to_merge_hours`` is ``None`` and ``timing_measured`` is False — measured-or-absent,
    never a fabricated latency.
    """
    findings = payload.get("adversarial_findings_count")
    model, resolved = model_from_payload(payload)
    cost = float(payload["cost"]) if _is_number(payload.get("cost")) else None
    phases = (
        int(payload["phases_total"])
        if _is_number(payload.get("phases_total"))
        else None
    )
    merge_state = str(payload.get("merge_state") or "").strip()
    timing_hours = None
    timing_measured = False
    if merge_state in MERGE_STATES:
        started = parse_timestamp(payload.get("started_at"))
        merged = parse_timestamp(payload.get("merged_at"))
        if started is not None and merged is not None and merged > started:
            timing_hours = (merged - started).total_seconds() / 3600.0
            timing_measured = True
    return {
        "spec_name": str(payload.get("spec_name") or "").strip(),
        "run_id": str(payload.get("run_id") or "").strip(),
        "verdict": str(payload.get("verdict") or "").strip(),
        "merge_state": merge_state,
        "model": model,
        "model_resolved": resolved,
        "cost_usd": cost,
        "phases_total": phases,
        "adversarial_findings_count": (
            int(findings) if _is_number(findings) else None
        ),
        "reviewed": _is_number(findings),
        "time_to_merge_hours": timing_hours,
        "timing_measured": timing_measured,
        "scope": str(payload.get("scope") or "").strip(),
    }


# ── The pure aggregation (recomputed from the records, never hand-written) ──


def _dedupe_waves(waves: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse multiple verdict records of the SAME run to the wave's current standing.

    The s3a version chain can re-derive one run as its permanence state advances (the same
    ``entity_id``, a re-keyed ``knowledge_id``); counting both versions would count one wave
    twice. Per ``run_id`` the most-advanced merge state wins (``published`` > ``merged`` > any
    other), ties broken by first occurrence (the read seam feeds files in deterministic order).
    """
    order: list[str] = []
    by_run: dict[str, dict[str, Any]] = {}
    for wave in waves:
        run_id = wave["run_id"]
        if run_id in by_run:
            current = by_run[run_id]
            rank_new = 2 if wave["merge_state"] in MERGE_STATES else 0
            rank_cur = 2 if current["merge_state"] in MERGE_STATES else 0
            if wave["merge_state"] == "published":
                rank_new = 3
            if current["merge_state"] == "published":
                rank_cur = 3
            if rank_new > rank_cur:
                by_run[run_id] = wave
        else:
            by_run[run_id] = wave
            order.append(run_id)
    return [by_run[run_id] for run_id in order]


def _timing_hours(waves: list[dict[str, Any]]) -> list[float]:
    """The measured time-to-merge hours across merged waves that carry their timing."""
    return [
        w["time_to_merge_hours"]
        for w in waves
        if w["merge_state"] in MERGE_STATES and w["timing_measured"]
    ]


def _totals(waves: list[dict[str, Any]]) -> dict[str, Any]:
    """The pooled measured rows over every completed wave.

    Each row is derived from the wave rows above; an absent backing field leaves the row's
    figure ``None`` (empty-but-valid), never a fabricated zero. The adversarial-finding row is
    a rate over the ADVERSARIALLY REVIEWED waves (the only waves whose review recorded a finding
    count — a wave without a review carries no finding measurement), reported alongside the
    review coverage so an unreviewed-heavy corpus reads honestly rather than as zero findings.
    """
    n = len(waves)
    merged = sum(1 for w in waves if w["merge_state"] in MERGE_STATES)
    costs = [w["cost_usd"] for w in waves if w["cost_usd"] is not None]
    phases = [w["phases_total"] for w in waves if w["phases_total"] is not None]
    reviewed = [w for w in waves if w["reviewed"]]
    findings = [w["adversarial_findings_count"] for w in reviewed if w["adversarial_findings_count"] is not None]
    timing = _timing_hours(waves)
    return {
        "waves_completed": n,
        "waves_merged": merged,
        "merge_rate": (
            _rounded(merged / n) if n else None
        ),
        "waves_reviewed": len(reviewed),
        "review_coverage": (_rounded(len(reviewed) / n) if n else None),
        "adversarial_findings_total": sum(findings),
        "adversarial_findings_per_reviewed_wave": (
            _rounded(sum(findings) / len(findings)) if findings else None
        ),
        "cost_per_wave_usd": {
            "mean": _rounded(_mean(costs)),
            "median": _rounded(_median(costs)),
            "n": len(costs),
        },
        "phases_per_wave": {
            "mean": _rounded(_mean(phases), 4),
            "median": _rounded(_median(phases), 4),
            "n": len(phases),
        },
        "time_to_merge_hours": {
            "mean": _rounded(_mean(timing), 4),
            "median": _rounded(_median(timing), 4),
            "merged_with_timing": len(timing),
        },
    }


def _per_model_rows(waves: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The per-model split: each model's own copy of the measured rows.

    Grouped by the RESOLVED canonical model id only. A wave whose scope yields no canonical
    model (unresolvable or outside the corpus vocabulary) is excluded here and named in
    coverage — the split never buckets a wave under a guessed or non-canonical key.
    """
    by_model: dict[str, list[dict[str, Any]]] = {}
    for wave in waves:
        if not wave["model_resolved"]:
            continue
        by_model.setdefault(wave["model"], []).append(wave)
    rows = []
    for model in sorted(by_model):
        sub = by_model[model]
        merged = sum(1 for w in sub if w["merge_state"] in MERGE_STATES)
        costs = [w["cost_usd"] for w in sub if w["cost_usd"] is not None]
        phases = [w["phases_total"] for w in sub if w["phases_total"] is not None]
        reviewed = [w for w in sub if w["reviewed"]]
        findings = [
            w["adversarial_findings_count"]
            for w in reviewed
            if w["adversarial_findings_count"] is not None
        ]
        timing = _timing_hours(sub)
        rows.append(
            {
                "model": model,
                "waves": len(sub),
                "merged": merged,
                "merge_rate": _rounded(merged / len(sub)) if sub else None,
                "waves_reviewed": len(reviewed),
                "adversarial_findings_per_reviewed_wave": (
                    _rounded(sum(findings) / len(findings)) if findings else None
                ),
                "cost_per_wave_usd": {
                    "mean": _rounded(_mean(costs)),
                    "median": _rounded(_median(costs)),
                    "n": len(costs),
                },
                "phases_per_wave": {
                    "mean": _rounded(_mean(phases), 4),
                    "median": _rounded(_median(phases), 4),
                    "n": len(phases),
                },
                "time_to_merge_hours": {
                    "mean": _rounded(_mean(timing), 4),
                    "median": _rounded(_median(timing), 4),
                    "merged_with_timing": len(timing),
                },
            }
        )
    return rows


def aggregate_scoreboard(waves: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate normalized wave rows into the scoreboard document body (pure, deterministic).

    ``waves`` is a list of :func:`normalize_wave` rows (already deduped per run). The body is
    exactly the deliverable's measured rows — the totals, the per-model split, the per-wave rows
    (so every total traces to a record), and the coverage the adversarial/read side needs.
    Deterministic for a fixed input: same rows in, same document out.
    """
    waves = _dedupe_waves(waves)
    totals = _totals(waves)
    merged_total = totals["waves_merged"]
    with_timing = totals["time_to_merge_hours"]["merged_with_timing"]
    unresolved = [w["run_id"] for w in waves if not w["model_resolved"]]
    return {
        "waves": [
            {
                "spec_name": w["spec_name"],
                "run_id": w["run_id"],
                "verdict": w["verdict"],
                "merge_state": w["merge_state"],
                "model": w["model"],
                "model_resolved": w["model_resolved"],
                "cost_usd": w["cost_usd"],
                "phases_total": w["phases_total"],
                "adversarial_findings_count": w["adversarial_findings_count"],
                "time_to_merge_hours": w["time_to_merge_hours"],
            }
            for w in waves
        ],
        "totals": totals,
        "per_model": _per_model_rows(waves),
        "coverage": {
            "waves": len(waves),
            "merged_waves": merged_total,
            "merged_with_timing": with_timing,
            "merged_timing_gap": merged_total - with_timing,
            "waves_without_model": len(unresolved),
            "unresolved_run_ids": unresolved[:20],
            "note": (
                "merge_state is the control-db state at the verdict's emission; a wave that "
                "merged after emission carries merged/published on its re-derived verdict "
                "version. time_to_merge is measured only over merged waves whose record carries "
                "the started_at/merged_at instants."
            ),
        },
    }


# ── The read seam (direct durable scan — the same pattern the session/decision/belief reads use) ──


def scoreboard_artifact_files(artifact_dir: Path) -> list[Path]:
    """Every ``*.json`` file under the records dir, in filename order (a missing dir is empty)."""
    if not artifact_dir.is_dir():
        return []
    return sorted(artifact_dir.glob("*.json"), key=lambda path: path.name)


_ARTIFACT_RECORD = "record"
_ARTIFACT_FOREIGN = "foreign"
_ARTIFACT_ANOMALY = "anomaly"


def _classify_artifact(
    path: Path, *, repository_id: str = REPOSITORY_ID
) -> tuple[str, dict[str, Any] | None]:
    """Classify ONE durable artifact file into ``(kind, payload)``.

    * ``"record"`` — a wave-verdict payload: either a ``wave-verdict/v1`` durable artifact of
      this repository (its ``text`` IS the payload) or a bare verdict payload document (a JSON
      object carrying ``spec_name``/``run_id``/``verdict``/``merge_state`` — the fixture form).
    * ``"foreign"`` — any other producer's artifact, a record of another repository, or an
      undecodable file. Skipped silently (the KB dir is shared by every producer).
    * ``"anomaly"`` — IS a ``wave-verdict/v1`` artifact but its payload is not readable. Surfaced
      as a warning — an honest signal, never a silent skip.
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return _ARTIFACT_FOREIGN, None
    try:
        artifact = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return _ARTIFACT_FOREIGN, None
    if not isinstance(artifact, dict):
        return _ARTIFACT_FOREIGN, None
    if artifact.get("extractor_version") == EXTRACTOR_VERSION:
        if artifact.get("repository_id") != repository_id:
            return _ARTIFACT_FOREIGN, None
        text = artifact.get("text")
        if not isinstance(text, str):
            return _ARTIFACT_ANOMALY, None
        try:
            payload = json.loads(text)
        except ValueError:
            return _ARTIFACT_ANOMALY, None
        if not isinstance(payload, dict):
            return _ARTIFACT_ANOMALY, None
        if not (payload.get("spec_name") and payload.get("run_id") and payload.get("verdict")):
            return _ARTIFACT_ANOMALY, None
        return _ARTIFACT_RECORD, payload
    if artifact.get("spec_name") and artifact.get("run_id") and artifact.get("verdict"):
        return _ARTIFACT_RECORD, artifact
    return _ARTIFACT_FOREIGN, None


def load_wave_payloads(
    artifact_dir: Path | None = None,
    *,
    repository_id: str = REPOSITORY_ID,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Scan a records dir for every wave-verdict payload: ``(payloads, warnings)``.

    ``artifact_dir`` defaults to the repo's durable KB artifact directory
    (``core.paths.KB_ARTIFACT_DIR`` — resolved at call time). ``warnings`` names the
    ``wave-verdict/v1`` artifacts that are not readable verdict records (the classifier's
    ``anomaly`` kind); foreign artifacts (every other producer's rows in the shared KB dir) are
    skipped silently.
    """
    from agentic_dynamics.core.paths import KB_ARTIFACT_DIR

    artifact_dir = artifact_dir or KB_ARTIFACT_DIR
    warnings: list[str] = []
    payloads: list[dict[str, Any]] = []
    for path in scoreboard_artifact_files(artifact_dir):
        kind, payload = _classify_artifact(path, repository_id=repository_id)
        if kind == _ARTIFACT_RECORD:
            payloads.append(payload)
        elif kind == _ARTIFACT_ANOMALY:
            warnings.append(
                f"{path.name}: a wave-verdict/v1 artifact that is not a readable wave-verdict "
                "record — excluded from the scoreboard aggregation"
            )
    return payloads, warnings


def build_scoreboard(
    records_dir: Path | None = None,
    *,
    repository_id: str = REPOSITORY_ID,
    now: datetime | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Recompute the scoreboard from the wave-verdict records: ``(document, warnings)``.

    The full aggregation: scan the records dir (default the durable KB artifact dir), normalize
    each classified verdict payload into a wave row, dedupe per run, and aggregate into the
    ``scoreboard/v1`` document. This is the ONLY path that produces the durable document's
    measured rows — the totals are recomputed here, never hand-written. ``now`` is injectable so
    a caller can pin ``generated_at`` (tests); production uses the real clock.
    """
    payloads, warnings = load_wave_payloads(records_dir, repository_id=repository_id)
    waves = [normalize_wave(payload) for payload in payloads]
    body = aggregate_scoreboard(waves)
    document = {
        "schema": "scoreboard/v1",
        "generated_at": (now or datetime.now(timezone.utc)).isoformat(),
        "producer": {"actor": ACTOR, "scope": aio_acl_scope(repository_id)},
        "recomputed_from": EXTRACTOR_VERSION,
        "records_dir": str(records_dir) if records_dir is not None else None,
        "body": body,
    }
    return document, warnings
