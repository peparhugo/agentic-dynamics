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
      "contract_version": "lab-contract/v2",
      "lab": "lab_story_arc.py",
      "input_dataset_id": "canonical_registry/story",
      "registry_identity_sha256": "…64 hex…",
      "resolved_input_sha256": "…64 hex…",
      "registry_version": "data-manifest/1.0+701rows",
      "metric_definition_version": "story_arc/v1",
      "data_integrity_policy": "docs/data_integrity_findings.md",
      "requires_external_service": null,
      "n_input_records": 215,
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

import re
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
#: renamed to ``registry_identity_sha256`` and ``resolved_input_sha256`` was added (P2).
CONTRACT_VERSION = "lab-contract/v2"

#: The key under which the contract is embedded in a lab's output JSON.
CONTRACT_KEY = "lab_contract"

#: The fields the review requires, verbatim (with the P2 rename + addition applied). The
#: guard tests assert exactly this set is present and non-empty
#: (``requires_external_service`` may legitimately be ``null``).
REQUIRED_FIELDS = (
    "input_dataset_id",
    "registry_identity_sha256",
    "resolved_input_sha256",
    "registry_version",
    "metric_definition_version",
    "data_integrity_policy",
    "requires_external_service",
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
    """The lineage block embedded in a publication-eligible lab's output JSON."""

    lab: str
    input_dataset_id: str
    registry_identity_sha256: str
    resolved_input_sha256: str
    registry_version: str
    metric_definition_version: str
    data_integrity_policy: str = DATA_INTEGRITY_POLICY
    requires_external_service: str | None = None
    n_input_records: int = 0
    contract_version: str = CONTRACT_VERSION
    generated_at: str = ""

    def to_dict(self) -> dict:
        """Plain dict for JSON embedding (field order preserved for readable diffs)."""
        return asdict(self)


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


def build_contract(
    lab_script: str,
    tables: CanonicalTables,
    *,
    n_input_records: int | None = None,
    now: datetime | None = None,
) -> dict:
    """Producer side: build the contract block for ``lab_script``'s output.

    ``tables`` is the :class:`CanonicalTables` the lab actually computed over — both
    identities (the registry selection hash and the payload-content hash) are taken from it
    rather than re-read, so the embedded values always describe the corpus the numbers came
    from, even if the manifest changes mid-run.

    ``n_input_records`` defaults to the total resolved rows; a lab that measures over a
    narrower slice should pass its own count so the contract reports what it truly used.
    """
    entry = _lab_entry(lab_script)
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    total = n_input_records
    if total is None:
        total = len(tables.stories) + len(tables.reviews) + len(tables.analysis)

    return LabContract(
        lab=lab_script,
        input_dataset_id=tables.input_dataset_id,
        registry_identity_sha256=tables.identity.registry_identity_sha256,
        resolved_input_sha256=tables.resolved_input_sha256,
        registry_version=tables.identity.registry_version,
        metric_definition_version=entry.metric_definition_version,
        data_integrity_policy=DATA_INTEGRITY_POLICY,
        requires_external_service=entry.requires_external_service,
        n_input_records=int(total),
        generated_at=stamp,
    ).to_dict()


def attach_contract(
    payload: dict,
    lab_script: str,
    tables: CanonicalTables,
    *,
    n_input_records: int | None = None,
) -> dict:
    """Embed the contract into a lab's output payload and return it (for chaining)."""
    payload[CONTRACT_KEY] = build_contract(lab_script, tables, n_input_records=n_input_records)
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
    # carry a real value. An empty hash is what a lab emits when it found no manifest.
    for field_name in REQUIRED_FIELDS:
        if field_name == "requires_external_service":
            continue
        if not str(block.get(field_name) or "").strip():
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

    return None
