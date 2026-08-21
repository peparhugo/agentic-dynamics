"""Lab classification manifest — the publication/reproduction gate for lab books.

Why this module exists
----------------------
``docs/review/semantic_integrity_review.md`` P0: the lab-book path bypassed the canonical
data-integrity boundary. ``build_data.py`` builds its principal corpus from current registry
rows (correct), but lab JSONs were loaded straight into ``apps/website/data.js`` with zero
provenance checks — while ten labs still read the **retired** ``_results_summary.json``. The
result was a split publication path: main metrics canonical, lab metrics legacy.

Release item 1 (quarantine) closes that immediately: every ``scripts/lab_*.py`` is classified
in ``scripts/lab_manifest.json``, and the two consumers of the lab set read their lists from
that one file through this module:

* ``scripts/reproduce.sh``  -> :func:`reproduce_lab_scripts` (the default/core lab set)
* ``scripts/build_data.py`` -> :func:`publication_labs` / :func:`rejection_reason` (publication)

Design notes
------------
* **Data lives in JSON, semantics live here.** The manifest is a hand-edited data file; this
  module is the only parser, so the reproduce set and the publication set can never drift
  apart the way two hand-kept lists did.
* **Dataclasses over dicts** (repo convention): callers get a typed :class:`LabEntry`.
* **Invariants are enforced at load time** (:func:`load_lab_manifest`), not merely asserted in
  a test, because a malformed manifest must fail the pipeline rather than silently publish.
  ``tests/test_lab_manifest.py`` additionally guards manifest-vs-disk-vs-consumer agreement.
* **No I/O beyond the manifest read**, so importing this module is cheap and side-effect free.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Repo root — this file is ``src/agentic_dynamics/reporting/lab_manifest.py``, so four parents up.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

#: The classification manifest. Lives beside the labs it classifies (``scripts/``) so the
#: manifest and the scripts move together.
MANIFEST_PATH = PROJECT_ROOT / "scripts" / "lab_manifest.json"

#: The three legal ``lab_status`` values (the review prescribes exactly these).
LAB_STATUSES = ("canonical", "historical", "quarantined")

#: Statuses that may never run in the default reproduction or reach the website.
#: A quarantined lab keeps its file (historical record) and stays runnable by hand via
#: ``agentic-dynamics analyze lab <name>`` — it is only removed from the *automatic* paths.
BLOCKED_STATUSES = ("quarantined",)


@dataclass(frozen=True)
class LabEntry:
    """One classified lab book.

    Attributes mirror ``field_semantics`` in the manifest; see that block for the contract.
    ``script`` is the file name (``lab_story_arc.py``) and ``name`` the CLI/lab short name
    (``story_arc``) used by ``agentic-dynamics analyze lab <name>``.
    """

    script: str
    lab_status: str
    publication_eligible: bool
    website_key: str | None
    reproduce_default: bool
    output: str | None
    input_sources: tuple[str, ...] = ()
    reads_retired_summary: bool = False
    requires_external_service: str | None = None
    contract_status: str = "pending"
    rationale: str = ""

    @property
    def name(self) -> str:
        """Short lab name: ``lab_story_arc.py`` -> ``story_arc``."""
        return self.script.removeprefix("lab_").removesuffix(".py")

    @property
    def quarantined(self) -> bool:
        """True when the lab is excluded from reproduction + publication."""
        return self.lab_status in BLOCKED_STATUSES

    @property
    def published(self) -> bool:
        """True when ``build_data.py`` should actually load this lab's JSON.

        Eligibility alone is not enough: a lab is loaded only when the site has somewhere to
        put it (``website_key``). This keeps the quarantine phase behaviour-preserving — it
        removes noncanonical sections without silently adding new ones.
        """
        return self.publication_eligible and self.website_key is not None


@dataclass(frozen=True)
class LabManifest:
    """The parsed manifest: an ordered mapping of script name -> :class:`LabEntry`."""

    schema_version: str
    entries: dict[str, LabEntry] = field(default_factory=dict)
    retired_sources: tuple[str, ...] = ()

    def __iter__(self) -> Iterator[LabEntry]:
        return iter(self.entries.values())

    def __len__(self) -> int:
        return len(self.entries)

    def get(self, script_or_name: str) -> LabEntry | None:
        """Look an entry up by script file name or by short lab name."""
        if script_or_name in self.entries:
            return self.entries[script_or_name]
        candidate = (
            f"lab_{script_or_name}.py" if not script_or_name.endswith(".py") else script_or_name
        )
        return self.entries.get(candidate)


def _coerce(script: str, raw: dict[str, Any]) -> LabEntry:
    """Build a :class:`LabEntry`, rejecting anything the schema does not allow."""
    status = raw.get("lab_status")
    if status not in LAB_STATUSES:
        raise ValueError(f"{script}: lab_status must be one of {LAB_STATUSES}, got {status!r}")

    entry = LabEntry(
        script=script,
        lab_status=status,
        publication_eligible=bool(raw.get("publication_eligible", False)),
        website_key=raw.get("website_key"),
        reproduce_default=bool(raw.get("reproduce_default", False)),
        output=raw.get("output"),
        input_sources=tuple(raw.get("input_sources", ())),
        reads_retired_summary=bool(raw.get("reads_retired_summary", False)),
        requires_external_service=raw.get("requires_external_service"),
        contract_status=raw.get("contract_status", "pending"),
        rationale=raw.get("rationale", ""),
    )

    # --- load-time invariants (the gate; a bad manifest must fail loudly) -----------------
    # 1. Quarantine is absolute: no reproduction, no publication. This is the property the
    #    whole phase exists to guarantee, so it is checked before any consumer sees the entry.
    if entry.quarantined and entry.publication_eligible:
        raise ValueError(f"{script}: quarantined labs cannot be publication_eligible")
    if entry.quarantined and entry.reproduce_default:
        raise ValueError(f"{script}: quarantined labs cannot be in the reproduce default set")
    # 2. A lab that touches the retired summary cannot be canonical, by definition.
    if entry.reads_retired_summary and entry.lab_status == "canonical":
        raise ValueError(
            f"{script}: reads the retired summary, so it cannot be lab_status=canonical"
        )
    # 3. Reaching the website requires eligibility (defence in depth against a typo flipping
    #    website_key on for a quarantined lab).
    if entry.website_key is not None and entry.quarantined and entry.published:
        raise ValueError(f"{script}: quarantined lab resolved as published")
    # 4. Rationale is mandatory — a classification without evidence is an opinion.
    if not entry.rationale.strip():
        raise ValueError(f"{script}: a classification needs a rationale")
    return entry


def load_lab_manifest(path: Path | None = None) -> LabManifest:
    """Parse and validate ``scripts/lab_manifest.json``.

    Raises ``FileNotFoundError`` if the manifest is missing and ``ValueError`` if any entry
    violates the schema — never returns a partially-valid manifest, because the callers use it
    to decide what gets published.
    """
    manifest_path = path or MANIFEST_PATH
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    labs = raw.get("labs")
    if not isinstance(labs, dict) or not labs:
        raise ValueError(f"{manifest_path}: 'labs' must be a non-empty object")
    entries = {script: _coerce(script, body) for script, body in sorted(labs.items())}
    return LabManifest(
        schema_version=raw.get("schema_version", "unknown"),
        entries=entries,
        retired_sources=tuple(raw.get("retired_sources", ())),
    )


def reproduce_lab_scripts(manifest: LabManifest | None = None) -> list[str]:
    """Script file names for the default (core) reproduction lab set, sorted.

    Consumed by ``scripts/reproduce.sh`` through this module's ``__main__`` CLI.
    """
    man = manifest or load_lab_manifest()
    return [e.script for e in man if e.reproduce_default]


def publication_labs(manifest: LabManifest | None = None) -> dict[str, LabEntry]:
    """``website_key -> LabEntry`` for every lab whose output may reach ``data.js``."""
    man = manifest or load_lab_manifest()
    return {e.website_key: e for e in man if e.published and e.website_key}


def quarantined_labs(manifest: LabManifest | None = None) -> list[LabEntry]:
    """Every quarantined lab — used by build_data to log rejections by name."""
    man = manifest or load_lab_manifest()
    return [e for e in man if e.quarantined]


def rejection_reason(script_or_name: str, manifest: LabManifest | None = None) -> str | None:
    """Why this lab may not be published, or ``None`` when it may be.

    ``build_data.py`` logs this string so a dropped website section is always traceable to a
    named lab and a stated reason, rather than silently disappearing.
    """
    man = manifest or load_lab_manifest()
    entry = man.get(script_or_name)
    if entry is None:
        return f"{script_or_name}: not classified in {MANIFEST_PATH.name}"
    if entry.quarantined:
        return f"{entry.script}: quarantined ({entry.rationale})"
    if not entry.publication_eligible:
        return f"{entry.script}: not publication_eligible (lab_status={entry.lab_status})"
    if entry.website_key is None:
        return f"{entry.script}: no website_key — nothing on the site consumes it"
    return None


def _main(argv: list[str] | None = None) -> int:
    """Tiny CLI so bash (``scripts/reproduce.sh``) shares this one parser.

    ``--reproduce``   one script file name per line (the core lab set)
    ``--publication`` one ``website_key=script`` pair per line
    ``--quarantined`` one script file name per line
    """
    import argparse

    parser = argparse.ArgumentParser(description="lab classification manifest queries")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--reproduce", action="store_true", help="default reproduction lab set")
    group.add_argument("--publication", action="store_true", help="publication-eligible labs")
    group.add_argument("--quarantined", action="store_true", help="quarantined labs")
    args = parser.parse_args(argv)

    manifest = load_lab_manifest()
    if args.reproduce:
        lines = reproduce_lab_scripts(manifest)
    elif args.publication:
        lines = [
            f"{key}={entry.script}" for key, entry in sorted(publication_labs(manifest).items())
        ]
    else:
        lines = [e.script for e in quarantined_labs(manifest)]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI shim
    raise SystemExit(_main())
