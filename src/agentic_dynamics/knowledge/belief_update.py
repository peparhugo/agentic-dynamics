"""The belief UPDATE operation + its wave-verdict trigger (loop 2, phase s4b_belief_update).

This module is phase ``s4b_belief_update``'s substrate (``self_knowledge_layer`` wave, design
``docs/designs/proposed/self_knowledge_layer.md``): the missing half of the Bayesian engine the
s4a type (``knowledge/belief_ingestion.py``) records. The s4a record carries a hypothesis with
``n_confirmations`` / ``n_disconfirmations`` / ``posterior_confidence`` — but nothing ever
increments them. This module is that increment:

* the **UPDATE operation** — when a wave outcome bears on a hypothesis, the record is UPDATED
  in place (``n_confirmations +1`` or ``n_disconfirmations +1``, posterior recomputed through the
  SAME deterministic rule the type uses, :func:`belief_ingestion.compute_posterior`), NEVER
  duplicated: the updated record is a NEW VERSION of the SAME belief entity (``entity_id`` /
  ``logical_locator`` hold; ``knowledge_id`` re-keys) whose ``supersedes`` names the version it
  replaces — "two confirm updates yield ONE record with n=2". The prior stays the record's own
  anchor (``prior_confidence`` is the confidence the AIO held before the recorded evidence
  arrived; the counts are the accumulating frequentist evidence), so the posterior moves toward
  the evidence with each confirmation and a disconfirmation lowers it — never a fresh prior on
  every update;
* the **TRIGGER** — the s3b wave-verdict emission (a completed spec run's verdict, emitted at
  the run-completion terminal write in ``scripts/run_workflow.py``) CONSULTS the belief index
  and updates the hypotheses it bears on. The **belief index** is the AIO's org-root pool of
  current belief records resolved from the durable KB artifacts (latest version per belief
  entity — the same direct read ``session_ingestion`` uses, never the registry projection). A
  verdict BEARS ON a belief when the belief's own ``evidence_citations`` name the outcome's wave
  (its ``spec_name`` and/or ``run_id`` — the s4c seeds "exist with ... citations [the wave names
  that bear on it]"); an outcome no belief cites updates NOTHING.

**Confirm vs disconfirm is the AIO's Bayesian judgment, not a mechanical parse.** The same
positive outcome disconfirms a pessimist seed ("findings were opt-in and never produced" was
disconfirmed by kb_finding_layer's own success) while confirming an optimist one — a polarity
that cannot be read off hypothesis phrasing. The trigger therefore takes its polarity from a
documented DEFAULT for positive-form empirical generalizations (:func:`verdict_signal`: a green
verdict — ``merge-ready`` / ``clean`` — confirms the hypotheses it bears on; ``not``
disconfirms), overridable per call via ``signal_fn(belief_payload, verdict_payload)`` so the AIO
can register the honest judgment for a negatively-phrased hypothesis. The update OPERATION
itself takes the signal explicitly — the tests that prove "a disconfirm lowers the posterior"
call it directly, never through an invented derivation.

**Rerun-safe, never double-counted.** The index skips a belief that already counts the outcome's
exact run (its citations name ``run_id``): re-emitting the same run's verdict — a re-drain, a
re-run of the terminal write — does not increment the same hypothesis twice. Distinct outcomes
that bear on the same belief each update it once, appending their own citation.

Actor + scope follow the s4a record and the design's actor table: producer aio, org-root
``org:<repository_id>`` scope (structurally and in the payload). The records this module writes
are the same ``source_type=belief`` ADVISORY/``[H]`` records ``belief_ingestion`` builds (a
belief is the AIO's self-reported posterior about the machine operating) — the module adds NO
source type, it only advances existing belief entities. A cell/workload scope never resolves
them.

Scope fence: the UPDATE operation + its trigger ONLY — the seeded initial corpus is s4c
(``belief_ingestion`` stays the type; nothing here writes to the KB or registers a command). The
module is pure w.r.t. the durable store: ``record_to_artifact`` / publish decisions stay with
the caller (the outbox payloads are built at the composition root in ``scripts/run_workflow.py``,
exactly as the s3b verdict's are).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field as _dataclass_field
from datetime import datetime
from pathlib import Path
from typing import Any

from agentic_dynamics.knowledge import belief_ingestion as bi
from agentic_dynamics.knowledge.knowledge import (
    KnowledgeEvent,
    KnowledgeRecord,
)
from agentic_dynamics.knowledge.knowledge_ingestion import (
    REPOSITORY_ID,
    record_to_event,
)
from agentic_dynamics.knowledge.record_factory import _now_iso
from agentic_dynamics.knowledge.session_ingestion import aio_acl_scope

# ── Extractor contract constants ────────────────────────────────

#: The two update signals the protocol knows. ``confirm`` increments ``n_confirmations`` (the
#: posterior moves toward the evidence); ``disconfirm`` increments ``n_disconfirmations`` (the
#: posterior lowers). Anything else is a caller error, not a silent no-op.
SIGNALS = ("confirm", "disconfirm")

#: The s4b reuses the s4a type's source_type/extractor — an updated belief is the SAME
#: ``belief`` family (the s4a ``belief/v1`` extractor), never a new record class: the entity
#: identity and the version chain are the point, and a second extractor would fork the family.
SOURCE_TYPE = bi.SOURCE_TYPE
EXTRACTOR_VERSION = bi.EXTRACTOR_VERSION
ACTOR = bi.ACTOR


# ── The pure UPDATE operation (in place, never duplicated) ──────


def update_belief(
    current: dict[str, Any],
    *,
    signal: str,
    citation: str | None = None,
    last_updated: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return the NEXT canonical payload for the SAME belief slot after ONE outcome.

    ``current`` is a belief payload dict (the s4a canonical shape — ``hypothesis`` / ``domain`` /
    ``prior_confidence`` / the two counts / ``last_updated`` / ``evidence_citations`` / …; a raw
    seed dict is normalized through :func:`belief_ingestion.belief_payload` first, so an
    unvalidated caller cannot corrupt the math). ``signal`` is ``"confirm"`` or ``"disconfirm"``.

    The update rule, read back through the type's own deterministic posterior function::

        prior stays the record's anchor (the AIO's confidence BEFORE the recorded evidence);
        n_confirmations += 1  when signal == "confirm"   # posterior moves toward the evidence
        n_disconfirmations += 1 when signal == "disconfirm"  # a disconfirm LOWERS it
        posterior_confidence = compute_posterior(prior, n_confirmations, n_disconfirmations)

    The prior is deliberately preserved: the record's ``prior_confidence`` is the anchor the
    counts accumulate against (a Beta-binomial with the prior as pseudo-observations), so two
    confirmations on a 0.5 prior yield ONE belief whose posterior is 0.75 — exactly the s4a
    well-formedness fixture, never a re-anchored guess on every update.

    ``citation`` (optional) is appended to ``evidence_citations`` — the new outcome's name, the
    running evidence the belief counts; an exact duplicate is not re-appended. ``last_updated``
    (optional) advances the record's place on the revision timeline (defaults to the derivation
    instant — ``now`` / the wall-clock); two updates MUST carry different ``last_updated``
    values or they collapse into one version (the same bytes → the same ``knowledge_id``).

    Returns a NEW dict — the input is never mutated — so the s4b record seam can hand it to
    :func:`belief_ingestion.build_belief_record` for a new VERSION of the same entity.
    """
    if signal not in SIGNALS:
        raise ValueError(f"belief update signal must be one of {SIGNALS}, got {signal!r}")
    base = bi.belief_payload(current)  # normalize + validate: required fields, confidences, counts
    n_confirm = base["n_confirmations"] + (1 if signal == "confirm" else 0)
    n_disconfirm = base["n_disconfirmations"] + (1 if signal == "disconfirm" else 0)
    citations = list(base["evidence_citations"])
    if citation and citation not in citations:
        citations.append(citation)
    updated = dict(base)
    updated.update(
        {
            "n_confirmations": n_confirm,
            "n_disconfirmations": n_disconfirm,
            "evidence_citations": citations,
            "last_updated": last_updated or _now_iso(now),
        }
    )
    updated["posterior_confidence"] = bi.compute_posterior(
        base["prior_confidence"], n_confirm, n_disconfirm
    )
    return updated


def version_record(
    current_payload: dict[str, Any],
    *,
    supersedes: str | None,
    signal: str,
    citation: str | None = None,
    repository_id: str = REPOSITORY_ID,
    last_updated: str | None = None,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Build the NEW VERSION record of a belief slot after one update (never a duplicate).

    ``current_payload`` is the belief's current canonical payload and ``supersedes`` the current
    version's ``knowledge_id`` (the durable artifact's filename stem — the durable artifacts
    blank the id field, so the filename IS the id). The returned record shares the current
    entity (``belief_id``/``logical_locator``/``entity_id`` are pure functions of
    ``domain | hypothesis``, which the update preserves) while re-keying ``knowledge_id`` from
    the advanced body — the version chain the "updated in place, NEVER duplicated" rule needs.
    ``supersedes`` is folded into the record BEFORE the factory computes ``content_hash`` (see
    :func:`belief_ingestion.build_belief_record`), so the durable artifact — which serializes
    the link verbatim — is exactly the bytes the hash covers.

    Authority stays the s4a nominal: the updated record is the same ADVISORY/``[H]``
    self-reported belief, org-root scoped, carrying its own declared ``evidence_class`` in the
    body.
    """
    updated = update_belief(
        current_payload,
        signal=signal,
        citation=citation,
        last_updated=last_updated,
        now=now,
    )
    return bi.build_belief_record(
        updated,
        repository_id=repository_id,
        now=now,
        supersedes=supersedes,
    )


def version_from_record(
    record: KnowledgeRecord,
    *,
    signal: str,
    citation: str | None = None,
    now: datetime | None = None,
) -> KnowledgeRecord:
    """Version ONE durable belief record in place — the record-level update seam.

    ``record`` is the current belief record (its ``text`` is the canonical payload, its
    ``knowledge_id`` the predecessor the new version supersedes). Returns the updated VERSION of
    the SAME belief entity: ``entity_id`` identical, ``supersedes`` = ``record.knowledge_id``,
    ``n_confirmations``/``n_disconfirmations`` advanced by the signal, posterior recomputed.
    This is the seam the DONE_WHEN asserts on: two confirm calls on the same record chain to ONE
    entity whose current version carries ``n_confirmations == 2``.
    """
    return version_record(
        json.loads(record.text),
        supersedes=record.knowledge_id,
        signal=signal,
        citation=citation,
        repository_id=record.repository_id,
        now=now,
    )


# ── The wave-verdict trigger helpers ────────────────────────────


def verdict_signal(verdict: str) -> str:
    """The DEFAULT polarity of one wave verdict for a positive-form empirical hypothesis.

    The corpus's wave-verdict vocabulary is ``merge-ready`` / ``clean`` / ``not`` (the s3a
    ``wave_verdict_ingestion.VERDICTS``). For a hypothesis phrased as a positive empirical
    generalization ("flash converges in ~1 wave on in-process work"), a GREEN verdict — the wave
    converged, merged, or cleaned — is a CONFIRMATION (the generalization held again) and a
    ``not`` verdict is a DISCONFIRMATION. This is the documented default the trigger applies;
    a negatively-phrased hypothesis (the AIO's pessimist seeds) inverts at the call site via
    ``signal_fn`` — polarity is the AIO's judgment, never a mechanical text parse.
    """
    if verdict == "not":
        return "disconfirm"
    return "confirm"


def _verdict_fields(verdict_payload: dict[str, Any]) -> tuple[str, str, str]:
    """Extract + validate the three outcome identity fields of a wave-verdict payload."""
    spec_name = str(verdict_payload.get("spec_name") or "").strip()
    run_id = str(verdict_payload.get("run_id") or "").strip()
    verdict = str(verdict_payload.get("verdict") or "").strip()
    if not spec_name or not run_id or not verdict:
        raise ValueError(
            "a wave-verdict payload needs spec_name/run_id/verdict to consult the belief index"
        )
    return spec_name, run_id, verdict


def _cites_wave(payload: dict[str, Any], spec_name: str, run_id: str) -> bool:
    """Whether a belief's citations name the outcome's wave (spec_name and/or run_id).

    The s4c seeds "exist with ... citations [the wave names that bear on it]" — e.g. a seed
    cites ``"kb_finding_layer wave verdict"`` (wave-level) or
    ``"self_knowledge_layer wave verdict run-77f7b899f4f8"`` (run-level). A verdict for spec
    ``kb_finding_layer`` matches the first; a verdict for that exact run matches the second.
    Either match means the outcome BEARS ON the hypothesis — it is a new observation in the
    same evidence series the belief already counts.
    """
    for citation in payload.get("evidence_citations") or []:
        text = str(citation).lower()
        if spec_name.lower() in text or run_id.lower() in text:
            return True
    return False


def _already_counts(payload: dict[str, Any], run_id: str) -> bool:
    """Whether a belief already counted this EXACT outcome (its citations name ``run_id``).

    The rerun-safety half of the trigger: re-emitting the same run's verdict — a re-drain, a
    re-run of the terminal write — must not double-increment a hypothesis. Wave-level citations
    (no run id) leave the door open for a NEW run of the same spec; once a run-level citation is
    present, that exact outcome is counted and a re-application is skipped.
    """
    for citation in payload.get("evidence_citations") or []:
        if run_id.lower() in str(citation).lower():
            return True
    return False


# ── The belief index (the durable current-belief pool) ───────────


def belief_artifact_files(artifact_dir: Path) -> list[Path]:
    """Every ``*.json`` file under the durable artifact dir, in filename order.

    Mirrors ``session_ingestion.session_artifact_files``: the artifact dir is shared by every
    producer, so the belief family is found by content (below), never by a guessable filename.
    A missing dir (a fresh checkout with no KB yet) is simply empty — the pre-seed state in
    which a verdict consults an index that holds nothing and updates nothing.
    """
    if not artifact_dir.is_dir():
        return []
    return sorted(artifact_dir.glob("*.json"), key=lambda path: path.name)


def _classify_belief_artifact(
    path: Path, *, repository_id: str = REPOSITORY_ID
) -> tuple[str, dict[str, Any] | None]:
    """Classify ONE durable artifact file into ``(kind, payload)``.

    * ``"record"`` — an AIO org-root belief record (``extractor_version`` ``belief/v1``, the org
      ``repository_id``, a body whose ``actor``/``scope`` are the AIO's). ``payload`` is the
      decoded content body (the record's ``text``).
    * ``"foreign"`` — any other producer's artifact (the ``extractor_version`` discriminator), a
      record of another repository (the scope pre-filter), or an undecodable file. Skipped
      silently — the dir holds every family's rows and only THIS org's beliefs are candidates.
    * ``"anomaly"`` — IS a ``belief/v1`` artifact of this org but is NOT a readable AIO org-root
      belief: a corrupt artifact or a foreign-actor body. Surfaced as a warning — an honest
      signal, never a silent skip.

    The durable artifact blanks ``knowledge_id``/``content_hash`` and the volatile clocks, so
    the belief's current ``knowledge_id`` is the FILENAME stem (see the caller).
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return "foreign", None
    try:
        artifact = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return "foreign", None
    if not isinstance(artifact, dict):
        return "foreign", None
    if artifact.get("extractor_version") != EXTRACTOR_VERSION:
        return "foreign", None
    if artifact.get("repository_id") != repository_id:
        return "foreign", None
    text = artifact.get("text")
    if not isinstance(text, str):
        return "anomaly", None
    try:
        payload = json.loads(text)
    except ValueError:
        return "anomaly", None
    if not isinstance(payload, dict):
        return "anomaly", None
    if payload.get("actor") != ACTOR:
        return "anomaly", None
    if payload.get("scope") != aio_acl_scope(repository_id):
        return "anomaly", None
    return "record", payload


def scan_belief_payloads(
    *, repository_id: str = REPOSITORY_ID, artifact_dir: Path | None = None
) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
    """Scan the durable artifact dir for every AIO org-root belief payload.

    Returns ``(entries, warnings)`` where each entry is ``(knowledge_id, payload)`` — the
    durable artifact's filename stem IS the record's ``knowledge_id`` (the artifact blanks the
    field, exactly as ``session_ingestion`` reads its spine) — for one ``belief/v1`` record of
    this org, and ``warnings`` names the org-scoped ``belief/v1`` artifacts that are NOT
    readable AIO org-root beliefs (the classifier's ``anomaly`` kind). ``artifact_dir`` defaults
    to the repo's durable KB artifact directory (``core.paths.KB_ARTIFACT_DIR`` — resolved at
    call time so tests can redirect it).
    """
    from agentic_dynamics.core.paths import KB_ARTIFACT_DIR

    artifact_dir = artifact_dir or KB_ARTIFACT_DIR
    warnings: list[str] = []
    entries: list[tuple[str, dict[str, Any]]] = []
    for path in belief_artifact_files(artifact_dir):
        kind, payload = _classify_belief_artifact(path, repository_id=repository_id)
        if kind == "record":
            entries.append((path.stem, payload))
        elif kind == "anomaly":
            warnings.append(
                f"{path.name}: a belief/v1 artifact that is not a readable AIO org-root "
                "belief record — excluded from the belief index"
            )
    return entries, warnings


def belief_index(
    *, repository_id: str = REPOSITORY_ID, artifact_dir: Path | None = None
) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
    """Resolve the CURRENT belief index: the latest version of each belief entity.

    The durable dir accumulates every version an in-place update writes (each re-keys
    ``knowledge_id`` while ``entity_id`` holds), so the index must resolve ONE current payload
    per entity — the version a verdict consults and the one it supersedes. Resolution is by the
    belief's OWN revision content, never the filesystem wall-clock alone: greatest
    ``last_updated`` first, filename tie-break (checkout-stable, like
    ``session_ingestion._selection_key``). Returns ``(current, warnings)`` — ``current`` is the
    latest payload per belief entity (grouped by the type's ``belief_id`` — sha256 of
    ``domain|hypothesis`` — re-derived from the body, since the payload carries no
    ``logical_locator`` field) and ``warnings`` the scan anomalies.
    """
    entries, warnings = scan_belief_payloads(repository_id=repository_id, artifact_dir=artifact_dir)
    latest: dict[str, tuple[str, dict[str, Any]]] = {}
    for knowledge_id, payload in entries:
        # The payload body carries no ``logical_locator`` — the durable record's locator IS the
        # belief_id (sha256 of domain|hypothesis), so it is re-derived here from the body's own
        # fields. Two hypotheses in the same domain are therefore DIFFERENT entities (the type's
        # own identity rule), never one bucket.
        locator = bi.belief_id(str(payload.get("domain") or ""), str(payload.get("hypothesis") or ""))
        prev = latest.get(locator)
        if prev is None or (str(payload.get("last_updated") or ""), knowledge_id) > (
            str(prev[1].get("last_updated") or ""),
            prev[0],
        ):
            latest[locator] = (knowledge_id, payload)
    return sorted(latest.values(), key=lambda item: item[0]), warnings


# ── The trigger: a verdict consults the index and updates ───────


@dataclass
class BeliefUpdateResult:
    """What one :func:`apply_wave_verdict` consultation did.

    ``spec_name``/``run_id`` echo the outcome the verdict described. ``consulted`` is the number
    of current belief entities the index held; ``bearing`` how many of those the verdict bore on
    (their citations name the wave). ``updated`` lists the new VERSION records written for the
    bearing hypotheses (each supersedes its current version — the in-place update, never a
    duplicate); ``signals`` lists, in lockstep with ``updated``, the polarity each update
    applied (``confirm``/``disconfirm``) — the caller needs it to say WHY the record moved (a
    mixed-history belief's counts alone cannot name the latest direction). ``already_counted``
    counts the bearing hypotheses that had already counted this exact run (skipped — rerun-safe);
    ``unrelated`` is ``consulted - bearing`` — the outcome updated nothing there. ``warnings``
    lists the index scan's anomalies.
    """

    spec_name: str
    run_id: str
    consulted: int = 0
    bearing: int = 0
    updated: list[KnowledgeRecord] = _dataclass_field(default_factory=list)
    signals: list[str] = _dataclass_field(default_factory=list)
    already_counted: int = 0
    unrelated: int = 0
    warnings: list[str] = _dataclass_field(default_factory=list)


def apply_wave_verdict(
    verdict_payload: dict[str, Any],
    *,
    artifact_dir: Path | None = None,
    repository_id: str = REPOSITORY_ID,
    observed_at: str | None = None,
    signal_fn: Callable[[dict[str, Any], dict[str, Any]], str] | None = None,
    now: datetime | None = None,
) -> BeliefUpdateResult:
    """THE trigger (s4b): consult the belief index and update the hypotheses a verdict bears on.

    Called when a completed run's wave verdict lands (the s3b emission path in
    ``scripts/run_workflow.py``). ``verdict_payload`` is the s3a wave-verdict payload
    (``spec_name``/``run_id``/``verdict`` + the measured fields). The verdict:

    1. resolves the CURRENT belief index (latest version per durable belief entity, org scope);
    2. for each current belief, decides whether the outcome BEARS ON it — the belief's
       ``evidence_citations`` name the outcome's ``spec_name`` and/or ``run_id``
       (:func:`_cites_wave`). An outcome no belief cites updates NOTHING (``unrelated``);
    3. for each bearing belief, applies the update IN PLACE — a new VERSION of the SAME entity
       (``supersedes`` = the current version's id), never a duplicate. A bearing belief that
       already counts this exact run (a re-emitted verdict) is SKIPPED, not double-counted;
    4. the polarity (confirm vs disconfirm) is :func:`verdict_signal` over the verdict word by
       default, or the caller's ``signal_fn(belief_payload, verdict_payload)`` when one is given
       (the AIO's judgment for a negatively-phrased hypothesis).

    ``observed_at`` (optional) is the run's completion instant — the updated belief's
    ``last_updated`` (its place on the revision timeline is the run that revised it, not the
    producer wall-clock). ``artifact_dir`` defaults to the repo's durable KB artifact dir,
    resolved at call time so the composition root's tests can redirect it. The returned records
    are the durable payloads' ``record`` half; the caller publishes them (outbox, artifact
    first, operation ``supersede``) exactly as the s3b verdict is published.
    """
    spec_name, run_id, verdict = _verdict_fields(verdict_payload)
    current, warnings = belief_index(repository_id=repository_id, artifact_dir=artifact_dir)
    result = BeliefUpdateResult(
        spec_name=spec_name,
        run_id=run_id,
        consulted=len(current),
        warnings=warnings,
    )
    for knowledge_id, payload in current:
        if not _cites_wave(payload, spec_name, run_id):
            result.unrelated += 1
            continue
        result.bearing += 1
        if _already_counts(payload, run_id):
            result.already_counted += 1
            continue
        if signal_fn is not None:
            signal = signal_fn(payload, verdict_payload)
        else:
            signal = verdict_signal(verdict)
        if signal not in SIGNALS:
            raise ValueError(
                f"signal_fn returned {signal!r} for {spec_name} ({run_id}) — "
                f"must be one of {SIGNALS}"
            )
        result.updated.append(
            version_record(
                payload,
                supersedes=knowledge_id,
                signal=signal,
                citation=_outcome_citation(spec_name, run_id),
                repository_id=repository_id,
                last_updated=observed_at,
                now=now,
            )
        )
        result.signals.append(signal)
    return result


def _outcome_citation(spec_name: str, run_id: str) -> str:
    """The run-level citation an update appends: ``<spec> wave verdict <run>``.

    The same shape the s4a fixture citations carry ("self_knowledge_layer wave verdict
    run-77f7b899f4f8") — run-level, so a later re-emission of the SAME run is recognised as
    already counted while a NEW run of the same spec still bears on the hypothesis.
    """
    return f"{spec_name} wave verdict {run_id}"


def supersede_reason(verdict_payload: dict[str, Any], signal: str) -> str:
    """The registry/event reason for one belief supersession.

    Names the outcome that moved the belief and what it did: the verdict word + the signal the
    trigger APPLIED (``signal`` comes from the trigger result's lockstep ``signals`` list — never
    guessed from the updated record's counts, which accumulate a mixed history and cannot name
    the latest direction).
    """
    return (
        f"wave {verdict_payload.get('spec_name')} ({verdict_payload.get('run_id')}) "
        f"verdict {verdict_payload.get('verdict')} {signal}ed this hypothesis"
    )


def update_event(record: KnowledgeRecord, *, reason: str = "") -> KnowledgeEvent:
    """The pointer event for an updated belief version — ``operation=supersede``.

    An in-place update is a version chain, so the event that announces the new version is a
    ``supersede`` linking it to the predecessor (the record's ``supersedes``), not a fresh
    ``upsert``. ``reason`` names the wave outcome that moved the belief (see
    :func:`supersede_reason`).
    """
    return record_to_event(record, operation="supersede", reason=reason)
