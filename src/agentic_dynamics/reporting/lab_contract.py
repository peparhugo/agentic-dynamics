"""The canonical lab contract — provable lineage on every published lab output.

Why this module exists
----------------------
``docs/review/semantic_integrity_review.md`` P0, required correction:

    A publication-eligible lab must carry ``input_dataset_id``,
    ``registry_identity_sha256``, ``registry_version``, ``metric_definition_version``,
    ``data_integrity_policy``, ``requires_external_service``. […] ``build_data.py``
    rejects lab JSON whose embedded hash does not match the current manifest.

Phase s1 decided *which* labs may publish (``scripts/lab_manifest.json``). This module
decides *whether a given output file is still allowed to* — because eligibility is a
property of the lab, and freshness is a property of the artifact. A lab that was
publication-eligible yesterday produced a JSON that is stale today if records have since
been added, superseded, or tombstoned.

The contract is a single ``lab_contract`` block embedded in the lab's output JSON:

.. code-block:: json

    "lab_contract": {
      "contract_version": "lab-contract/v4",
      "lab": "lab_story_arc.py",
      "input_dataset_id": "canonical_registry/story",
      "registry_identity_sha256": "…64 hex…",
      "resolved_input_sha256": "…64 hex…",
      "registry_version": "data-manifest/1.0+701rows",
      "metric_definition_version": "story_arc/v1",
      "data_integrity_policy": "docs/data_integrity_findings.md",
      "requires_external_service": null,
      "n_resolved_records": 215,
      "n_eligible_records": 215,
      "n_used_records": 215,
      "n_excluded_records": 0,
      "n_unused_eligible_records": 0,
      "review_without_current_story": 0,
      "story_without_review": 0,
      "missing_required_field": 0,
      "outside_analysis_population": 0,
      "generated_at": "…"
    }

Two halves, deliberately in one module so they cannot drift:

* :func:`build_contract` — the **producer** side, called by each lab.
* :func:`validate_contract` — the **consumer** side, called by ``build_data.py`` before a
  lab's numbers are allowed onto the website.

Two identities (review P1 + P2)
-------------------------------
The contract carries *two* hashes, each answering a different question:

* ``registry_identity_sha256`` (was ``input_manifest_sha256``) — the *selection* a lab
  consumed: ``schema_version`` + the registry array. It changes when records are added,
  superseded, or tombstoned, and it does **not** change when a payload file's bytes do.
* ``resolved_input_sha256`` — the *content* a lab consumed: a stable sorted sequence of
  ``(table, entity_id, knowledge_id, payload-content digest)`` over every resolved payload.
  It changes precisely when a payload's measured content changes (see
  ``canonical_corpus.resolved_input_identity``), closing the P2 gap where the registry
  hash alone could not detect payload drift.

Validation is now **semantic** (review P1), not just presence + hash: every field that has
an authoritative source is compared against it exactly — ``lab`` and
``metric_definition_version`` and ``requires_external_service`` against the manifest entry,
``data_integrity_policy`` and ``contract_version`` against this module's constants,
``input_dataset_id`` against the tables the manifest entry declares, and
``registry_version`` against the current identity.

Design notes
------------
* ``metric_definition_version`` is authored in ``scripts/lab_manifest.json``, not in the
  lab source, so a metric redefinition (e.g. the s4 Grit resolution) is a one-line bump in
  the place that already records the classification. There is **no** ``<lab>/v0`` fallback:
  an unclassified lab cannot build a contract at all (it has no authoritative metric
  version), rather than being stamped with a value that is merely *visibly* provisional.
* Validation returns a *reason string* rather than raising: the publication gate must log
  and skip one bad lab, never abort the whole website build.
* An absent contract is treated exactly like a stale one. "Old lab output from before the
  contract existed" and "lab output built against a different corpus" are the same risk.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .canonical_corpus import (
    CanonicalTables,
    ManifestIdentity,
    current_manifest_identity,
)
from .lab_manifest import LabEntry, load_lab_manifest

#: Version of the contract schema itself. Bumped to v2 when ``input_manifest_sha256`` was
#: renamed to ``registry_identity_sha256`` and ``resolved_input_sha256`` was added (P2); to
#: v3 when ``n_input_records`` was replaced by the four-way record-count scope; and to v4
#: when the permissive ``eligible=resolved``/``used=eligible`` defaults were removed, the
#: eligible→used gap became explicit (``n_unused_eligible_records``), and the free-form
#: ``exclusions`` dict became the four named exclusion-reason counts — public-truth review
#: P1, phase p3. Bumped to v5 in m4 (measurement-contribution closure) when
#: ``metric_source_sha256`` was added — the hash of the lab's own source file, so a
#: contract attests to *which code* computed the metric, not just which corpus fed it.
CONTRACT_VERSION = "lab-contract/v5"

#: The key under which the contract is embedded in a lab's output JSON.
CONTRACT_KEY = "lab_contract"

#: The exclusion reasons a lab may declare (public-truth review P1, phase p3). The four
#: counts must sum to ``n_excluded_records`` — a lab cannot drop a record without saying
#: which of these four reasons dropped it. This is the *complete* vocabulary, so any lab
#: with a new reason must extend this tuple (and the reconciliation tests) rather than
#: smuggle a reason through a free-form dict.
EXCLUSION_REASONS = (
    "review_without_current_story",
    "story_without_review",
    "missing_required_field",
    "outside_analysis_population",
)

#: The fields the review requires, verbatim (with the P2 rename/addition and the p3
#: record-scope fields applied). The guard tests assert exactly this set is present and
#: non-empty (``requires_external_service`` may legitimately be ``null``; the four reason
#: counts may legitimately be ``0``).
REQUIRED_FIELDS = (
    "input_dataset_id",
    "registry_identity_sha256",
    "resolved_input_sha256",
    "registry_version",
    "metric_definition_version",
    "metric_source_sha256",
    "data_integrity_policy",
    "requires_external_service",
    "n_resolved_records",
    "n_eligible_records",
    "n_used_records",
    "n_excluded_records",
    "n_unused_eligible_records",
    *EXCLUSION_REASONS,
)

#: The authoritative data-integrity policy every publication-eligible lab declares it
#: follows (no-op condition relabel, tombstone exclusion, no fabricated values).
DATA_INTEGRITY_POLICY = "docs/data_integrity_findings.md"

#: Extracts the source type from a manifest ``input_sources`` entry such as
#: ``registry:data_manifest.json#registry (story, current)`` — the first word after the
#: open paren is the table name (``analysis joined on current story rows`` -> "analysis").
_INPUT_SOURCE_TABLE_RE = re.compile(r"\(([a-z_]+)")

#: The table names a publication lab may declare. Kept in sync with
#: ``canonical_corpus.TABLES`` so a typo'd source type is caught rather than hashed.
_TABLES = ("story", "finding", "review", "analysis")


@dataclass(frozen=True)
class LabContract:
    """The lineage block embedded in a publication-eligible lab's output JSON.

    The five record-count fields (review P2, phase c4; extended in p3) replace the single
    ``n_input_records`` and close the "declared used but actually used less" gap:
    ``n_resolved_records`` is what the resolver produced, ``n_eligible_records`` the subset
    that qualifies for the metric, ``n_used_records`` the subset the computation actually
    consumed, ``n_excluded_records`` the resolved-minus-eligible gap, and
    ``n_unused_eligible_records`` the eligible-but-not-consumed gap. The four exclusion
    reason counts (:data:`EXCLUSION_REASONS`) itemise *why* records were excluded.
    """

    lab: str
    input_dataset_id: str
    registry_identity_sha256: str
    resolved_input_sha256: str
    registry_version: str
    metric_definition_version: str
    metric_source_sha256: str
    n_resolved_records: int
    n_eligible_records: int
    n_used_records: int
    n_excluded_records: int
    n_unused_eligible_records: int
    review_without_current_story: int = 0
    story_without_review: int = 0
    missing_required_field: int = 0
    outside_analysis_population: int = 0
    data_integrity_policy: str = DATA_INTEGRITY_POLICY
    requires_external_service: str | None = None
    contract_version: str = CONTRACT_VERSION
    generated_at: str = ""

    def to_dict(self) -> dict:
        """Plain dict for JSON embedding (field order preserved for readable diffs)."""
        return asdict(self)


@dataclass(frozen=True)
class ContributionReport:
    """The computation's *self-report* of which records it consumed (m3).

    The review's P1 finding was that record-scope contracts were "explicit, but not proven
    against computation": the validator checked the counts *added up*, not that they
    described the records that actually contributed. This dataclass closes that gap — the
    lab's ``compute()`` returns it alongside the result payload, and the contract is
    DERIVED from it (:func:`attach_contribution`), never hand-authored afterwards.

    The five counts obey two invariants (enforced by :meth:`of`):

    * ``eligible + excluded == resolved`` — every resolved record is either eligible for
      the metric or excluded (with a reason);
    * ``used + unused_eligible == eligible`` — every eligible record is either consumed or
      declared unused.

    ``exclusion_reasons`` itemises ``excluded`` with exactly the :data:`EXCLUSION_REASONS`
    vocabulary, and ``used_record_ids`` is the stable identity of every record the
    computation actually consumed (its length is ``used``, so the "used" count is derived
    from real records rather than asserted).
    """

    resolved: int
    eligible: int
    used: int
    excluded: int
    unused_eligible: int
    exclusion_reasons: dict[str, int]
    used_record_ids: tuple[str, ...]

    @classmethod
    def of(
        cls,
        *,
        used_record_ids: Iterable[str],
        unused_eligible: int = 0,
        exclusion_reasons: dict[str, int] | None = None,
    ) -> ContributionReport:
        """Build a report from the used records, the unused-eligible gap, and the exclusions.

        The ``resolved`` total is *derived* (``used + unused_eligible + excluded``), which
        forces the caller to account for every resolved record — a lab that drops a record
        without naming it produces a ``resolved`` that no longer matches the resolver, and
        the existing registry-consistency test rejects the artifact.
        """
        used_ids = tuple(sorted(used_record_ids))
        reasons = {k: int(v) for k, v in (exclusion_reasons or {}).items() if int(v)}
        used = len(used_ids)
        excluded = sum(reasons.values())
        eligible = used + unused_eligible
        resolved = eligible + excluded
        return cls(
            resolved=resolved,
            eligible=eligible,
            used=used,
            excluded=excluded,
            unused_eligible=unused_eligible,
            exclusion_reasons=reasons,
            used_record_ids=used_ids,
        )


def record_id(payload: dict) -> str:
    """The stable identity of a resolved payload — ``entity_id`` (else ``knowledge_id``).

    A ``story``/``review``/``finding`` payload carries its registry ``entity_id``; an
    ``analysis`` payload carries its story's (it is a derived view). The id is what a lab
    puts into :class:`ContributionReport.used_record_ids` so the "used" count is auditable.
    """
    reg = payload.get("_registry") or {}
    return str(reg.get("entity_id") or reg.get("knowledge_id") or "")


def expected_tables(entry: LabEntry) -> tuple[str, ...]:
    """The resolver tables a lab reads, parsed from its declared ``input_sources``.

    Each ``input_sources`` entry is ``registry:data_manifest.json#registry (<table>, …)``;
    the first word after the open paren is the table name. This is the authoritative expected
    slice — the thing ``input_dataset_id`` and ``resolved_input_sha256`` are validated
    against, so the manifest entry (not the lab's own claim) decides what the lab reads.
    """
    tables: list[str] = []
    for source in entry.input_sources:
        match = _INPUT_SOURCE_TABLE_RE.search(source)
        if match and match.group(1) in _TABLES:
            tables.append(match.group(1))
    return tuple(tables)


def expected_dataset_id(entry: LabEntry) -> str:
    """The ``input_dataset_id`` a lab reading ``entry``'s tables *should* embed."""
    tables = expected_tables(entry)
    return f"canonical_registry/{'+'.join(tables)}" if tables else "canonical_registry"


def _lab_entry(lab_script: str) -> LabEntry:
    """Look a lab up in the manifest — raising (no ``<lab>/v0`` fallback) when absent.

    A lab that is not classified has no authoritative ``metric_definition_version``, so its
    contract cannot be built. Inventing ``<lab>/v0`` made an unclassified lab look merely
    provisional rather than invalid — the review's P1 called that out; this removes it.
    """
    entry = load_lab_manifest().get(lab_script)
    if entry is None:
        raise ValueError(
            f"{lab_script}: not classified in scripts/lab_manifest.json — a contract needs "
            f"the manifest's metric_definition_version (no <lab>/v0 fallback)"
        )
    if not entry.metric_definition_version.strip():
        raise ValueError(f"{lab_script}: manifest entry declares no metric_definition_version")
    return entry


def _resolved_count(tables: CanonicalTables) -> int:
    """The number of payloads the resolver produced for THIS lab's table slice.

    The default ``n_resolved_records`` — what the resolver handed the lab, summed over the
    tables the lab actually requested (not the whole four-table corpus).
    """
    return sum(len(tables.rows(t)) for t in tables.tables)


def lab_source_sha256(lab_script: str) -> str:
    """``sha256`` of the lab's own source file (m4) — the *code* that computed the metric.

    Every lab lives at ``scripts/<lab_script>``. Hashing its bytes lets a contract attest
    to *which code* produced the numbers — a metric re-implementation is visible even when
    the corpus and the metric_definition_version are unchanged.
    """
    path = Path(__file__).resolve().parents[3] / "scripts" / lab_script
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_contract(
    lab_script: str,
    tables: CanonicalTables,
    *,
    n_resolved_records: int | None = None,
    n_eligible_records: int | None = None,
    n_used_records: int | None = None,
    n_excluded_records: int | None = None,
    n_unused_eligible_records: int | None = None,
    review_without_current_story: int = 0,
    story_without_review: int = 0,
    missing_required_field: int = 0,
    outside_analysis_population: int = 0,
    now: datetime | None = None,
) -> dict:
    """Producer side: build the contract block for ``lab_script``'s output.

    ``tables`` is the :class:`CanonicalTables` the lab actually computed over — both
    identities (the registry selection hash and the payload-content hash) are taken from it
    rather than re-read, so the embedded values always describe the corpus the numbers came
    from, even if the manifest changes mid-run.

    The record-count scope (review P2, tightened in public-truth P1/p3): ``n_resolved_records``
    defaults to what the resolver produced for this slice; ``n_eligible_records`` and
    ``n_used_records`` are **required** — the permissive "everything resolved is eligible is
    used" defaults are removed, so a lab that drops records must say how many and why. The
    excluded/unused gaps are derived (``resolved - eligible`` / ``eligible - used``) but may
    be overridden; the four exclusion-reason counts itemise ``n_excluded_records``.
    """
    entry = _lab_entry(lab_script)
    stamp = (now or datetime.now(timezone.utc)).isoformat()

    resolved = int(
        n_resolved_records if n_resolved_records is not None else _resolved_count(tables)
    )

    # ── permissive defaults removed (public-truth review P1, phase p3) ────────────────
    # A lab must declare its eligibility and usage scope. "Everything resolved is eligible
    # is used" was exactly the defect the review found (condition_effects declared
    # 457/457/457/0 while its rows consumed only 215 stories + 155 reviews).
    if n_eligible_records is None:
        raise ValueError(
            f"{lab_script}: n_eligible_records is required — declare the eligible subset "
            f"(the permissive eligible=resolved default was removed)"
        )
    if n_used_records is None:
        raise ValueError(
            f"{lab_script}: n_used_records is required — declare the consumed subset "
            f"(the permissive used=eligible default was removed)"
        )
    eligible = int(n_eligible_records)
    used = int(n_used_records)
    excluded = int(n_excluded_records if n_excluded_records is not None else (resolved - eligible))
    unused = int(
        n_unused_eligible_records if n_unused_eligible_records is not None else (eligible - used)
    )

    return LabContract(
        lab=lab_script,
        input_dataset_id=tables.input_dataset_id,
        registry_identity_sha256=tables.identity.registry_identity_sha256,
        resolved_input_sha256=tables.resolved_input_sha256,
        registry_version=tables.identity.registry_version,
        metric_definition_version=entry.metric_definition_version,
        metric_source_sha256=lab_source_sha256(lab_script),
        n_resolved_records=resolved,
        n_eligible_records=eligible,
        n_used_records=used,
        n_excluded_records=excluded,
        n_unused_eligible_records=unused,
        review_without_current_story=int(review_without_current_story),
        story_without_review=int(story_without_review),
        missing_required_field=int(missing_required_field),
        outside_analysis_population=int(outside_analysis_population),
        data_integrity_policy=DATA_INTEGRITY_POLICY,
        requires_external_service=entry.requires_external_service,
        generated_at=stamp,
    ).to_dict()


def attach_contract(
    payload: dict,
    lab_script: str,
    tables: CanonicalTables,
    *,
    n_resolved_records: int | None = None,
    n_eligible_records: int | None = None,
    n_used_records: int | None = None,
    n_excluded_records: int | None = None,
    n_unused_eligible_records: int | None = None,
    review_without_current_story: int = 0,
    story_without_review: int = 0,
    missing_required_field: int = 0,
    outside_analysis_population: int = 0,
) -> dict:
    """Embed the contract into a lab's output payload and return it (for chaining)."""
    payload[CONTRACT_KEY] = build_contract(
        lab_script,
        tables,
        n_resolved_records=n_resolved_records,
        n_eligible_records=n_eligible_records,
        n_used_records=n_used_records,
        n_excluded_records=n_excluded_records,
        n_unused_eligible_records=n_unused_eligible_records,
        review_without_current_story=review_without_current_story,
        story_without_review=story_without_review,
        missing_required_field=missing_required_field,
        outside_analysis_population=outside_analysis_population,
    )
    return payload


def attach_contribution(
    payload: dict,
    lab_script: str,
    tables: CanonicalTables,
    contribution: ContributionReport,
) -> dict:
    """Embed a contract DERIVED from the computation's :class:`ContributionReport` (m3).

    The pattern is ``result, contribution = compute(...); attach_contribution(result, LAB,
    tables, contribution)`` — the contract's record scope comes from the computation, never
    from counts hand-authored in ``main`` afterwards. Each :data:`EXCLUSION_REASONS` count
    is read from ``contribution.exclusion_reasons``; a reason the report does not name is 0.
    """
    reasons = contribution.exclusion_reasons
    payload[CONTRACT_KEY] = build_contract(
        lab_script,
        tables,
        n_resolved_records=contribution.resolved,
        n_eligible_records=contribution.eligible,
        n_used_records=contribution.used,
        n_excluded_records=contribution.excluded,
        n_unused_eligible_records=contribution.unused_eligible,
        review_without_current_story=reasons.get("review_without_current_story", 0),
        story_without_review=reasons.get("story_without_review", 0),
        missing_required_field=reasons.get("missing_required_field", 0),
        outside_analysis_population=reasons.get("outside_analysis_population", 0),
    )
    return payload


def validate_contract(
    payload: dict,
    *,
    manifest_entry: LabEntry,
    current_identity: ManifestIdentity | None = None,
    manifest_path: Path | None = None,
    expected_resolved_input_sha256: str | None = None,
) -> str | None:
    """Consumer side: ``None`` when the payload may be published, else the reason it may not.

    Checks, in order (first failure wins, because later checks assume earlier ones):

    1. the contract block exists at all;
    2. every one of the required fields is present;
    3. the identity fields are non-empty (``requires_external_service`` excepted — ``None``
       is the correct value for a lab with no external dependency);
    4. **semantic identity** (review P1) — exact equality on every field with an
       authoritative source: ``lab`` / ``metric_definition_version`` /
       ``requires_external_service`` against ``manifest_entry``, ``data_integrity_policy`` /
       ``contract_version`` against this module's constants, and ``input_dataset_id`` against
       the tables ``manifest_entry`` declares;
    5. ``registry_version`` and ``registry_identity_sha256`` against the identity of the
       manifest on disk **now**;
    6. ``resolved_input_sha256`` against the caller-recomputed payload-content hash, when the
       caller supplies it (``build_data`` recomputes it by resolving the lab's own tables).

    Returns a human-readable reason so the gate can log it with the lab name.
    """
    block = payload.get(CONTRACT_KEY)
    if not isinstance(block, dict):
        return (
            f"{manifest_entry.script}: no '{CONTRACT_KEY}' block — the output predates the "
            f"canonical lab contract; re-run the lab"
        )

    missing = [f for f in REQUIRED_FIELDS if f not in block]
    if missing:
        return f"{manifest_entry.script}: contract is missing required field(s) {missing}"

    # `requires_external_service` is legitimately null; every other identity field must
    # carry a real value. An empty *string* hash/version is what a lab emits when it found
    # no manifest; a numeric count of ``0`` (``n_excluded_records`` for a no-exclusion lab)
    # and an empty ``exclusions`` dict are both real values, not absences.
    for field_name in REQUIRED_FIELDS:
        if field_name == "requires_external_service":
            continue
        value = block.get(field_name)
        if value is None:
            return f"{manifest_entry.script}: contract field '{field_name}' is empty"
        if isinstance(value, str) and not value.strip():
            return f"{manifest_entry.script}: contract field '{field_name}' is empty"

    # ── semantic identity: exact equality on every manifest-authored / constant field ──
    for field_name, expected in (
        ("lab", manifest_entry.script),
        ("input_dataset_id", expected_dataset_id(manifest_entry)),
        ("metric_definition_version", manifest_entry.metric_definition_version),
        ("data_integrity_policy", DATA_INTEGRITY_POLICY),
        ("requires_external_service", manifest_entry.requires_external_service),
        ("contract_version", CONTRACT_VERSION),
    ):
        if block.get(field_name) != expected:
            return (
                f"{manifest_entry.script}: contract field '{field_name}' is "
                f"{block.get(field_name)!r}, expected {expected!r}"
            )

    # ── metric source identity (m4): the contract attests to WHICH code computed it ──────
    current_source = lab_source_sha256(manifest_entry.script)
    if str(block.get("metric_source_sha256") or "") != current_source:
        return (
            f"{manifest_entry.script}: metric_source_sha256 mismatch — the lab's source "
            f"changed since the artifact was written; re-run the lab"
        )

    identity = (
        current_identity
        if current_identity is not None
        else current_manifest_identity(manifest_path)
    )
    if not identity.registry_identity_sha256:
        return (
            f"{manifest_entry.script}: no current data_manifest.json registry to validate "
            f"against — run scripts/generate_manifest.py"
        )

    # ── registry selection identity (the stale check, under its P2 name) ────────────────
    if str(block.get("registry_version") or "") != identity.registry_version:
        return (
            f"{manifest_entry.script}: registry_version {block.get('registry_version')!r} "
            f"!= current {identity.registry_version!r}"
        )
    embedded = str(block.get("registry_identity_sha256") or "")
    if embedded != identity.registry_identity_sha256:
        return (
            f"{manifest_entry.script}: stale registry_identity_sha256 "
            f"({embedded[:12]}… != current {identity.registry_identity_sha256[:12]}…) — "
            f"re-run the lab against the current registry"
        )

    # ── payload-content identity (review P2) — verified only when the caller recomputed it ─
    if expected_resolved_input_sha256 is not None:
        embedded_content = str(block.get("resolved_input_sha256") or "")
        if embedded_content != expected_resolved_input_sha256:
            return (
                f"{manifest_entry.script}: resolved_input_sha256 mismatch "
                f"({embedded_content[:12]}… != expected {expected_resolved_input_sha256[:12]}…) "
                f"— the payload content drifted; re-run the lab"
            )

    # ── record-count scope is self-consistent (review P2, phase c4; tightened in p3) ─────
    # resolved = eligible + excluded; eligible = used + unused_eligible; and the four
    # exclusion-reason counts must itemise every excluded record. A contract that sums
    # wrong, or that hides an eligible-but-unused gap, is exactly the "declared used but
    # actually used less" defect the review named.
    resolved = block.get("n_resolved_records", 0)
    eligible = block.get("n_eligible_records", 0)
    used = block.get("n_used_records", 0)
    excluded = block.get("n_excluded_records", 0)
    unused = block.get("n_unused_eligible_records", 0)
    try:
        resolved_i, eligible_i, used_i, excluded_i, unused_i = (
            int(resolved),
            int(eligible),
            int(used),
            int(excluded),
            int(unused),
        )
        reason_counts = {reason: int(block.get(reason, 0) or 0) for reason in EXCLUSION_REASONS}
    except (TypeError, ValueError):
        return f"{manifest_entry.script}: contract record-count fields must be integers"
    if eligible_i + excluded_i != resolved_i:
        return (
            f"{manifest_entry.script}: record counts inconsistent — "
            f"n_eligible ({eligible_i}) + n_excluded ({excluded_i}) != n_resolved ({resolved_i})"
        )
    if used_i + unused_i != eligible_i:
        return (
            f"{manifest_entry.script}: record counts inconsistent — "
            f"n_used ({used_i}) + n_unused_eligible ({unused_i}) != n_eligible ({eligible_i})"
        )
    reason_total = sum(reason_counts.values())
    if reason_total != excluded_i:
        return (
            f"{manifest_entry.script}: exclusion reasons sum to {reason_total}, "
            f"but n_excluded_records is {excluded_i}"
        )

    return None
