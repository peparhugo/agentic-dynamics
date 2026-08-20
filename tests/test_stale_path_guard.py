"""Stale-path guard (refactor-repair P0-2 guard).

Rejects retired path families in every ``status: accepted`` document (and every
``docs/designs/current/*`` design) unless the occurrence sits in the explicit historical
allowlist below. The retired families are the pre-refactor locations the repair release
retired:

====================  ==========================
retired               current
====================  ==========================
``src/instrument/``   ``src/agentic_dynamics/``
``experiments/configs/``  ``experiments/definitions/configs/``
``admin/server.py``   ``apps/control_room/server.py``
``firebase/public/``  ``apps/website/``
``code_reviews/2026-08-14_*``  ``docs/designs/current/2026-08-14_*``
====================  ==========================

An accepted doc that names one of these as a *current* location is a bug: accepted docs are
runtime context given to the agents that modify the repo. Historical discussion (reviews of the
pre-refactor tree, consolidation release records, rebrand/survey/verify docs that describe the
move) is legitimate ONLY via an explicit per-path allowlist entry — never a blanket exception.
A new accepted doc, or a new retired-family mention in an already-allowlisted doc, fails here.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RETIRED_PATH_FAMILIES: tuple[str, ...] = (
    "src/instrument/",
    "experiments/configs/",
    "admin/server.py",
    "firebase/public/",
    "code_reviews/2026-08-14",
)

#: Sentinel: a directory-prefix entry that may discuss any retired family (historical record).
_ALL = frozenset(RETIRED_PATH_FAMILIES)

#: Explicit historical allowlist. A key is either an exact repo-relative path, or a directory
#: prefix ending in ``/`` that applies to every file beneath it. The value is the set of retired
#: families that path may mention. Every entry is a deliberate historical discussion, justified
#: by the comment above it — not a current-state description.
ALLOWLIST: dict[str, frozenset[str]] = {
    # The architectural authority documents the retired monolith's decommission in §1 ("the old
    # src/instrument/", "src/instrument/ no longer exists") — historical, not a current path.
    "ARCHITECTURE.md": frozenset({"src/instrument/"}),
    # --- directories of historical records (critiques, release logs, research) ---
    "docs/review/": _ALL,                # external/internal critiques of the pre-refactor tree
    "docs/consolidation/": _ALL,         # S0–S6 release records (describe the move itself)
    "docs/control_room_ui/": frozenset({"src/instrument/", "admin/server.py"}),
    "docs/context_abstraction/": frozenset({"src/instrument/"}),
    "docs/spec_lifecycle/": frozenset({"src/instrument/"}),
    # --- rebrand + website archaeology (firebase/public/ → apps/website/, src/instrument/) ---
    "docs/agentic_dynamics_arxiv_draft.md": frozenset({"src/instrument/", "firebase/public/", "code_reviews/2026-08-14"}),
    "docs/agentic_dynamics_rebrand_plan.md": frozenset({"src/instrument/", "firebase/public/"}),
    "docs/agentic_dynamics_rebrand_verify.md": frozenset({"firebase/public/"}),
    "docs/architecture_visual.md": frozenset({"firebase/public/"}),
    "docs/facelift.md": frozenset({"firebase/public/"}),
    "docs/fixplan.md": frozenset({"src/instrument/", "admin/server.py", "firebase/public/"}),
    "docs/narrative.md": frozenset({"firebase/public/"}),
    "docs/redesign.md": frozenset({"firebase/public/"}),
    "docs/remediation_plan.md": frozenset({"src/instrument/", "experiments/configs/", "firebase/public/"}),
    "docs/remediation_verify.md": frozenset({"src/instrument/", "firebase/public/"}),
    "docs/verify_evidence.md": frozenset({"firebase/public/"}),
    "docs/verify_evidence_redesign.md": frozenset({"firebase/public/"}),
    "docs/verify_framework.md": frozenset({"firebase/public/"}),
    # --- opencode docs refresh + Claude Code port (document the admin/server.py mapping) ---
    "docs/opencode_docs_challenge.md": frozenset({"src/instrument/"}),
    "docs/opencode_docs_scope.md": frozenset({"src/instrument/", "experiments/configs/", "admin/server.py", "code_reviews/2026-08-14"}),
    "docs/opencode_docs_spec.md": frozenset({"src/instrument/", "experiments/configs/", "admin/server.py", "code_reviews/2026-08-14"}),
    "docs/claude_code_port.md": frozenset({"admin/server.py"}),
    "docs/claude_tools_to_skills_scope.md": frozenset({"src/instrument/", "experiments/configs/", "admin/server.py"}),
    "docs/claude_tools_to_skills_verify.md": frozenset({"src/instrument/", "experiments/configs/", "admin/server.py"}),
    # --- routing design/survey/verify (predate the package rename + Control Room move) ---
    "docs/routing_design.md": frozenset({"src/instrument/", "admin/server.py", "code_reviews/2026-08-14"}),
    "docs/routing_follow_up_verify.md": frozenset({"src/instrument/"}),
    "docs/routing_next_steps.md": frozenset({"src/instrument/"}),
    "docs/routing_signal_store_notes.md": frozenset({"src/instrument/"}),
    "docs/routing_survey.md": frozenset({"src/instrument/", "admin/server.py", "firebase/public/", "code_reviews/2026-08-14"}),
    "docs/routing_verify.md": frozenset({"src/instrument/"}),
    # --- spec/scope/challenge/verify (pre-refactor design + verification) ---
    "docs/challenge.md": frozenset({"src/instrument/", "admin/server.py"}),
    "docs/scope.md": frozenset({"src/instrument/", "admin/server.py"}),
    "docs/spec.md": frozenset({"src/instrument/", "admin/server.py"}),
    "docs/verify.md": frozenset({"admin/server.py"}),
    # --- surveys / audits / verifies (analyze the pre-refactor tree) ---
    "docs/auto_posthoc_survey.md": frozenset({"src/instrument/"}),
    "docs/auto_posthoc_verify.md": frozenset({"src/instrument/"}),
    "docs/control_room_survey.md": frozenset({"src/instrument/", "admin/server.py"}),
    "docs/operator_audit.md": frozenset({"src/instrument/"}),
    "docs/operator_fix_verify.md": frozenset({"src/instrument/"}),
    "docs/workflow_phase_survey.md": frozenset({"src/instrument/", "admin/server.py"}),
    "docs/workflow_phase_verify.md": frozenset({"src/instrument/", "admin/server.py"}),
}


def _status(path: Path) -> str | None:
    """Return a markdown file's ``status`` frontmatter value, or ``None`` if absent."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    for line in text[4:end].splitlines():
        if line.startswith("status:"):
            return line.split(":", 1)[1].strip()
    return None


def _scan_targets() -> list[Path]:
    """Every accepted doc (root + ``docs/**``) plus every ``docs/designs/current/*`` design."""
    targets: set[Path] = set()
    for path in sorted(ROOT.glob("*.md")) + sorted((ROOT / "docs").rglob("*.md")):
        if _status(path) == "accepted":
            targets.add(path)
    for path in (ROOT / "docs" / "designs" / "current").glob("*.md"):
        targets.add(path)
    return sorted(targets)


def _is_allowed(rel: str, family: str) -> bool:
    """True when ``rel`` (or a directory prefix of it) explicitly allows ``family``."""
    for prefix, allowed in ALLOWLIST.items():
        is_dir_match = prefix.endswith("/") and rel.startswith(prefix)
        is_file_match = not prefix.endswith("/") and rel == prefix
        if (is_dir_match or is_file_match) and ("*" in allowed or family in allowed):
            return True
    return False


def test_accepted_docs_use_no_retired_paths():
    """No accepted/current doc names a retired path outside the explicit historical allowlist."""
    violations: list[str] = []
    for path in _scan_targets():
        rel = str(path.relative_to(ROOT))
        text = path.read_text(encoding="utf-8")
        for family in RETIRED_PATH_FAMILIES:
            if family in text and not _is_allowed(rel, family):
                violations.append(f"{rel}: {family!r} (retired — repoint or add an allowlist entry)")
    assert not violations, (
        "accepted/current docs referencing retired paths:\n"
        + "\n".join(sorted(violations))
    )


def test_allowlist_entries_all_resolve():
    """Every allowlist key names an existing file (or a non-empty directory prefix)."""
    for prefix in ALLOWLIST:
        if prefix.endswith("/"):
            assert (ROOT / prefix).is_dir(), f"allowlist dir prefix does not exist: {prefix}/"
        else:
            assert (ROOT / prefix).is_file(), f"allowlist file does not exist: {prefix}"
