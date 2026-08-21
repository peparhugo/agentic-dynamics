"""The canonical lab contract — provable lineage on every published lab output.

Why this module exists
----------------------
``docs/review/semantic_integrity_review.md`` P0, required correction:

    A publication-eligible lab must carry ``input_dataset_id``,
    ``input_manifest_sha256``, ``registry_version``, ``metric_definition_version``,
    ``data_integrity_policy``, ``requires_external_service``. […] ``build_data.py``
    rejects lab JSON whose embedded manifest hash does not match the current manifest.

Phase s1 decided *which* labs may publish (``scripts/lab_manifest.json``). This module
decides *whether a given output file is still allowed to* — because eligibility is a
property of the lab, and freshness is a property of the artifact. A lab that was
publication-eligible yesterday produced a JSON that is stale today if records have since
been added, superseded, or tombstoned.

The contract is a single ``lab_contract`` block embedded in the lab's output JSON:

.. code-block:: json

    "lab_contract": {
      "contract_version": "lab-contract/v1",
      "lab": "lab_story_arc.py",
      "input_dataset_id": "canonical_registry/story",
      "input_manifest_sha256": "…64 hex…",
      "registry_version": "data-manifest/1.0+701rows",
      "metric_definition_version": "story_arc/v1",
      "data_integrity_policy": "docs/data_integrity_findings.md",
      "requires_external_service": null,
      "n_input_records": 225,
      "generated_at": "…"
    }

Two halves, deliberately in one module so they cannot drift:

* :func:`build_contract` — the **producer** side, called by each lab.
* :func:`validate_contract` — the **consumer** side, called by ``build_data.py`` before a
  lab's numbers are allowed onto the website.

Design notes
------------
* ``metric_definition_version`` is authored in ``scripts/lab_manifest.json``, not in the
  lab source, so a metric redefinition (e.g. the s4 Grit resolution) is a one-line bump in
  the place that already records the classification.
* Validation returns a *reason string* rather than raising: the publication gate must log
  and skip one bad lab, never abort the whole website build.
* An absent contract is treated exactly like a stale one. "Old lab output from before the
  contract existed" and "lab output built against a different corpus" are the same risk.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .canonical_corpus import (
    CanonicalTables,
    ManifestIdentity,
    current_manifest_identity,
)

#: Version of the contract schema itself. Bump when a required field is added/renamed.
CONTRACT_VERSION = "lab-contract/v1"

#: The key under which the contract is embedded in a lab's output JSON.
CONTRACT_KEY = "lab_contract"

#: The six fields the review requires, verbatim. The guard tests assert exactly this set is
#: present and non-empty (``requires_external_service`` may legitimately be ``null``).
REQUIRED_FIELDS = (
    "input_dataset_id",
    "input_manifest_sha256",
    "registry_version",
    "metric_definition_version",
    "data_integrity_policy",
    "requires_external_service",
)

#: The authoritative data-integrity policy every publication-eligible lab declares it
#: follows (no-op condition relabel, tombstone exclusion, no fabricated values).
DATA_INTEGRITY_POLICY = "docs/data_integrity_findings.md"


@dataclass(frozen=True)
class LabContract:
    """The lineage block embedded in a publication-eligible lab's output JSON."""

    lab: str
    input_dataset_id: str
    input_manifest_sha256: str
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


def _metric_definition_version(lab_script: str) -> str:
    """Read the lab's metric-definition version from ``scripts/lab_manifest.json``.

    Kept in the manifest (one place) rather than in each lab, so bumping a metric
    definition is a single edit next to the classification that justifies it. Falls back to
    ``"<name>/v0"`` for an unclassified lab — a value that is *visibly* provisional rather
    than silently plausible.
    """
    from .lab_manifest import load_lab_manifest  # local import: avoids an import cycle

    entry = load_lab_manifest().get(lab_script)
    if entry is None:
        return f"{lab_script.removeprefix('lab_').removesuffix('.py')}/v0"
    return entry.metric_definition_version


def _requires_external_service(lab_script: str) -> str | None:
    """The lab's declared external-service dependency, from the manifest."""
    from .lab_manifest import load_lab_manifest  # local import: avoids an import cycle

    entry = load_lab_manifest().get(lab_script)
    return entry.requires_external_service if entry else None


def build_contract(
    lab_script: str,
    tables: CanonicalTables,
    *,
    n_input_records: int | None = None,
    now: datetime | None = None,
) -> dict:
    """Producer side: build the contract block for ``lab_script``'s output.

    ``tables`` is the :class:`CanonicalTables` the lab actually computed over — the
    identity is taken from it rather than re-read, so the embedded hash always describes
    the corpus the numbers came from, even if the manifest changes mid-run.

    ``n_input_records`` defaults to the total resolved rows; a lab that measures over a
    narrower slice should pass its own count so the contract reports what it truly used.
    """
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    total = n_input_records
    if total is None:
        total = len(tables.stories) + len(tables.reviews) + len(tables.analysis)

    return LabContract(
        lab=lab_script,
        input_dataset_id=tables.input_dataset_id,
        input_manifest_sha256=tables.identity.input_manifest_sha256,
        registry_version=tables.identity.registry_version,
        metric_definition_version=_metric_definition_version(lab_script),
        data_integrity_policy=DATA_INTEGRITY_POLICY,
        requires_external_service=_requires_external_service(lab_script),
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
    lab_script: str,
    current: ManifestIdentity | None = None,
    manifest_path: Path | None = None,
) -> str | None:
    """Consumer side: ``None`` when the payload may be published, else the reason it may not.

    Checks, in order (first failure wins, because later checks assume earlier ones):

    1. the contract block exists at all;
    2. every one of the six required fields is present;
    3. the identity fields are non-empty (``requires_external_service`` excepted — ``None``
       is the correct value for a lab with no external dependency);
    4. ``input_manifest_sha256`` equals the identity of the manifest on disk **now**.

    Returns a human-readable reason so the gate can log it with the lab name.
    """
    block = payload.get(CONTRACT_KEY)
    if not isinstance(block, dict):
        return (
            f"{lab_script}: no '{CONTRACT_KEY}' block — the output predates the canonical "
            f"lab contract; re-run the lab"
        )

    missing = [f for f in REQUIRED_FIELDS if f not in block]
    if missing:
        return f"{lab_script}: contract is missing required field(s) {missing}"

    # `requires_external_service` is legitimately null; every other identity field must
    # carry a real value. An empty hash is what a lab emits when it found no manifest.
    for field_name in REQUIRED_FIELDS:
        if field_name == "requires_external_service":
            continue
        if not str(block.get(field_name) or "").strip():
            return f"{lab_script}: contract field '{field_name}' is empty"

    identity = current if current is not None else current_manifest_identity(manifest_path)
    if not identity.input_manifest_sha256:
        return (
            f"{lab_script}: no current data_manifest.json registry to validate against — "
            f"run scripts/generate_manifest.py"
        )

    embedded = str(block.get("input_manifest_sha256"))
    if embedded != identity.input_manifest_sha256:
        return (
            f"{lab_script}: stale input_manifest_sha256 "
            f"({embedded[:12]}… != current {identity.input_manifest_sha256[:12]}…, "
            f"registry_version {block.get('registry_version')!r} vs "
            f"{identity.registry_version!r}) — re-run the lab against the current registry"
        )

    return None
