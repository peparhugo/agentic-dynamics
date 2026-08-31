"""Doc-lifecycle lint (consolidation Stage 0, phase `lifecycle`).

Enforces critique rec 4 (``docs/reviews/semantic_monolith_review.md``): every
top-level markdown document carries a structured lifecycle status, and the
``docs/archive/`` / ``docs/designs/`` trees carry the specific statuses the
migration table (``docs/release/consolidation/design.md`` §3) requires.

The status vocabulary (rec 4) is::

    proposed | accepted | implementing | implemented | superseded | abandoned

with optional ``supersedes:``, ``superseded_by:`` and ``implemented_by:`` fields.
The convention is a YAML front-matter block at the very top of each document::

    ---
    status: accepted
    superseded_by: ARCHITECTURE.md
    ---

This test walks ``docs/**`` + root ``*.md`` and asserts every file carries a
``status`` field, and that the archive/designs trees are correctly classified.
It is deliberately cheap and has no external dependencies.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

STATUS_VOCABULARY = frozenset({
    "proposed", "accepted", "implementing", "implemented", "superseded", "abandoned",
    "preregistered",
})


def _front_matter(path: Path) -> dict:
    """Parse the YAML front-matter block, if any, from a markdown file.

    A front-matter block is the first two ``---`` lines: everything between
    them is key-value (``key: value``) lines. Returns an empty dict when the
    file does not start with ``---``.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return {}
    meta: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta


def _markdown_files() -> list[Path]:
    """All root ``*.md`` files plus every ``*.md`` under ``docs/`` (recursive)."""
    files = sorted(ROOT.glob("*.md"))
    files += sorted((ROOT / "docs").rglob("*.md"))
    return files


def test_every_document_has_status_field():
    """Every root + docs markdown file carries a status field in the vocabulary."""
    missing = []
    for path in _markdown_files():
        meta = _front_matter(path)
        status = meta.get("status")
        if status is None:
            missing.append(f"{path.relative_to(ROOT)}: missing status field")
        elif status not in STATUS_VOCABULARY:
            missing.append(f"{path.relative_to(ROOT)}: unknown status {status!r}")
    assert not missing, "documents lacking a valid status field:\n" + "\n".join(missing)


def test_archive_entries_are_superseded():
    """Every ``docs/archive/`` entry is ``status: superseded`` with a successor."""
    problems = []
    for path in sorted((ROOT / "docs" / "archive").glob("*.md")):
        meta = _front_matter(path)
        if meta.get("status") != "superseded":
            problems.append(f"{path.relative_to(ROOT)}: status={meta.get('status')!r}, want superseded")
        if not meta.get("superseded_by"):
            problems.append(f"{path.relative_to(ROOT)}: missing superseded_by")
    assert not problems, "archive entries must be superseded + superseded_by:\n" + "\n".join(problems)


def test_kind_tree_statuses():
    """Every kind tree carries the status its home directory requires.

    The docs-taxonomy restructure (``docs/designs/proposed/docs_taxonomy_restructure.md`` §(d))
    retired ``docs/designs/current/`` as a path family: the *kind* is now carried by the
    directory (designs/verdicts/preregistrations/verification/…), the status by the frontmatter.
    Each kind home enforces exactly one status value — verdicts are ``accepted`` findings,
    preregistrations are ``accepted`` commitments, intake proposals are ``proposed``.
    """
    tree_status = {
        "docs/architecture/current": "accepted",
        "docs/experiments/designs": "accepted",
        "docs/experiments/preregistrations": "accepted",
        "docs/experiments/results": "accepted",
        "docs/postmortems": "accepted",
        "docs/verification": "accepted",
        "docs/website": "accepted",
        "docs/release": "accepted",
        "docs/reviews": "accepted",
        "docs/designs/proposed": "proposed",
    }
    problems = []
    for rel_dir, want in tree_status.items():
        for path in sorted((ROOT / rel_dir).glob("*.md")):
            meta = _front_matter(path)
            if meta.get("status") != want:
                problems.append(
                    f"{path.relative_to(ROOT)}: status={meta.get('status')!r}, want {want}"
                )
    assert not problems, "kind-tree status violations:\n" + "\n".join(problems)


def test_implemented_designs_name_their_branch():
    """Every ``docs/designs/implemented/`` entry is implemented + implemented_by."""
    problems = []
    for path in sorted((ROOT / "docs" / "designs" / "implemented").glob("*.md")):
        meta = _front_matter(path)
        if meta.get("status") != "implemented":
            problems.append(f"{path.relative_to(ROOT)}: status={meta.get('status')!r}, want implemented")
        if not meta.get("implemented_by"):
            problems.append(f"{path.relative_to(ROOT)}: missing implemented_by")
    assert not problems, "implemented designs must be implemented + implemented_by:\n" + "\n".join(problems)


def test_no_blueprint_at_root():
    """No BLUEPRINT*.md may remain at the repo root (they moved to docs/archive/)."""
    blueprints = sorted(ROOT.glob("BLUEPRINT*.md"))
    assert not blueprints, f"BLUEPRINT*.md still at root: {[p.name for p in blueprints]}"


# ── cap_stabilization_release p5 (hard rule 6): the CAP/control stale-language guard ──────────
#
# The review's P1 sharpest point: the authoritative docs described the CAP/control plane as
# "emerging"/"reserved-but-empty" while the modules are implemented and consumed by live campaigns
# (cap_2a/2b, cap_escalation_measurement, cap_session_routing_*). These two tests guard the
# rewritten language in BOTH directions: the detector fires on the legacy phrasing (fail-old) and
# the authoritative docs stay clean of it while the modules exist (pass-new).

#: Every CAP module the design's I0–I10 homes map to. The guard is vacuous if one is missing.
CAP_CONTROL_MODULES = (
    "src/agentic_dynamics/control/facts.py",
    "src/agentic_dynamics/control/fact_ingestion.py",
    "src/agentic_dynamics/control/context_compiler.py",
    "src/agentic_dynamics/control/step_routing.py",
    "src/agentic_dynamics/control/evidence_analyzer.py",
    "src/agentic_dynamics/control/checkpoint.py",
    "src/agentic_dynamics/control/rules.py",
    "src/agentic_dynamics/control/validator.py",
    "src/agentic_dynamics/control/decisions.py",
    "src/agentic_dynamics/control/reducers/pattern.py",
)

#: Phrases that CLAIM the plane is unimplemented. A historical reference quoted as "gone" is fine;
#: a present-tense claim is not. The frozen DESIGN doc is exempt — only the authoritative maps
#: (ARCHITECTURE.md, README.md, agent_config) are scanned.
STALE_CAP_PHRASES = (
    "reserved-but-empty",
    "reserved for CAP",
    "reserved home",
    "empty placeholder",
    "emerging control",
    "only emerging",
)

AUTHORITATIVE_DOCS = ("ARCHITECTURE.md", "README.md", "agent_config/mental-model.md")


def _stale_cap_hits(text: str) -> list[str]:
    """Return every stale CAP phrase present in ``text`` (lower-case, substring match)."""
    return [p for p in STALE_CAP_PHRASES if p.lower() in text.lower()]


def _cap_modules_implemented() -> bool:
    return all((ROOT / m).is_file() for m in CAP_CONTROL_MODULES)


def test_stale_cap_claims_absent_from_authoritative_docs():
    """PASS-on-new: while the CAP modules exist, the docs never call them reserved/empty/emerging."""
    if not _cap_modules_implemented():
        pytest.skip("CAP modules not present — guard vacuous")
    offenders = []
    for name in AUTHORITATIVE_DOCS:
        for phrase in _stale_cap_hits((ROOT / name).read_text(encoding="utf-8")):
            offenders.append(f"{name}: {phrase!r}")
    assert not offenders, "stale CAP/control claims remain in authoritative docs:\n" + "\n".join(
        offenders
    )


def test_stale_cap_claim_detector_fires_on_legacy_text():
    """FAIL-on-old: the exact pre-p5 phrasing is caught by the same detector."""
    legacy = [
        # ARCHITECTURE.md pre-p5 heading + table row
        "### Reserved-but-empty — the Context Abstraction Plane homes (CAP I0–I7)",
        "Each reserved home is an empty placeholder (module docstring + `# reserved for CAP I<n>`)",
        # agent_config/mental-model.md pre-p5 plane row
        "| `control` | emerging control — routing, signal store, supervisor, telemetry, queue steering, observation/actuation |",
        # README pre-p5 six-systems row
        "| **5. Emerging control** | Per-task/per-step model routing … | System 5 — emerging control |",
    ]
    for text in legacy:
        assert _stale_cap_hits(text), f"detector missed legacy phrasing: {text!r}"


# ── cap_stabilization_release p5 (hard rule 6): the README spec-count guard ───────────────────
#
# current_state item 5: README reported "124 (11 experiments + 113 workflows)" while
# experiments/specs/index.json held 125 (11 experiments + 114 workflows). The guard reconciles
# the README "By the Numbers" row against the generated lifecycle index — the authoritative count,
# never a remembered number.


def _spec_counts_from_index() -> tuple[int, int]:
    """(experiments, workflows) from the generated spec lifecycle index."""
    import json

    index = json.loads((ROOT / "experiments" / "specs" / "index.json").read_text(encoding="utf-8"))
    n_experiment = n_workflow = 0
    for spec in index.get("specs", []):
        kind = spec.get("artifact_kind")
        if kind == "experiment":
            n_experiment += 1
        elif kind == "workflow":
            n_workflow += 1
    return n_experiment, n_workflow


def _readme_spec_row() -> str:
    for line in (ROOT / "README.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("| Experiment + workflow specs |"):
            return line.strip()
    raise AssertionError("README 'By the Numbers' spec row not found")


def test_readme_spec_counts_match_index():
    """README's spec figure equals experiments/specs/index.json exactly."""
    n_experiment, n_workflow = _spec_counts_from_index()
    expected = (
        f"| Experiment + workflow specs | {n_experiment + n_workflow} "
        f"({n_experiment} experiments + {n_workflow} workflows) |"
    )
    assert _readme_spec_row() == expected, (
        f"README spec count drifted from experiments/specs/index.json: "
        f"{_readme_spec_row()!r} != {expected!r}"
    )
