"""Stale-path guard (refactor-repair P0-2 guard).

Rejects retired path families in every ``status: accepted`` document unless the
occurrence sits in the explicit historical allowlist below. The retired families
are the pre-refactor locations the repair release retired:

====================  ==========================
retired               current
====================  ==========================
``src/instrument/``   ``src/agentic_dynamics/``
``experiments/configs/``  ``experiments/definitions/configs/``
``admin/server.py``   ``apps/control_room/server.py``
``firebase/public/``  ``apps/website/``
``code_reviews/2026-08-14_*``  ``docs/architecture/current/2026-08-14_*``
====================  ==========================

An accepted doc that names one of these as a *current* location is a bug: accepted docs are
runtime context given to the agents that modify the repo. Historical discussion (reviews of the
pre-refactor tree, consolidation release records, rebrand/survey/verify docs that describe the
move) is legitimate ONLY via an explicit per-path allowlist entry — never a blanket exception.
A new accepted doc, or a new retired-family mention in an already-allowlisted doc, fails here.

The allowlist keys track the docs-taxonomy restructure
(``docs/designs/proposed/docs_taxonomy_restructure.md`` §(d)): every key lives at the file's
post-restructure home (``docs/reviews/``, ``docs/verification/``,
``docs/architecture/current/``, ``docs/experiments/*``, ``docs/website/``, ``docs/release/``).
"""

from __future__ import annotations

from pathlib import Path

import pytest
pytestmark = pytest.mark.fast

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
    "docs/release/consolidation/": _ALL,  # S0–S6 release records (describe the move itself)
    # --- reviews (external/internal critiques of the pre-refactor tree) ---
    "docs/reviews/architecture_review.md": frozenset({"src/instrument/", "admin/server.py"}),
    "docs/reviews/bugs.md": frozenset({"src/instrument/", "experiments/configs/"}),
    # authoring_product_aio wave reviews (2026-09-03): the preregistration + adversarial
    # docs describe the legacy src/instrument/workflow_runner.py path as the SUBJECT of
    # their findings (historical review prose about what no longer exists) — allowlisted
    # per the guard's documented per-path mechanism, not a blanket exception.
    "docs/reviews/authoring_product_aio_preregistration.md": frozenset({"src/instrument/"}),
    "docs/reviews/authoring_product_aio_adversarial.md": frozenset({"src/instrument/"}),
    "docs/reviews/code_review.md": frozenset({"src/instrument/", "admin/server.py"}),
    "docs/reviews/context_abstraction_review.md": frozenset({"src/instrument/"}),
    "docs/reviews/control_room.md": frozenset({"src/instrument/", "admin/server.py"}),
    "docs/reviews/refactor_repair_review.md": frozenset(
        {"src/instrument/", "experiments/configs/", "admin/server.py", "firebase/public/",
         "code_reviews/2026-08-14"}
    ),
    "docs/reviews/restructure.md": frozenset({"src/instrument/"}),
    "docs/reviews/semantic_integrity_review.md": frozenset({"admin/server.py"}),
    # The docs-refresh remediation REPORT records the anchors it repointed, so it necessarily
    # quotes the OLD `admin/server.py:NNN` anchors beside their `apps/control_room/**`
    # replacements. Every occurrence is a before-side citation in a fix log — the exact shape this
    # allowlist exists for. (Added by control_db_publication p5: the doc landed with the
    # remediation and the guard has been red since.)
    "docs/reviews/docs_architecture_refresh_remediation.md": frozenset({"admin/server.py"}),
    "docs/reviews/semantic_monolith_review.md": frozenset({"src/instrument/"}),
    "docs/reviews/website.md": frozenset({"src/instrument/", "firebase/public/"}),
    # --- Control Room surface material (documents the admin/server.py mapping) ---
    "docs/website/control_room_ui/": frozenset(
        {"src/instrument/", "admin/server.py", "firebase/public/"}
    ),
    # --- rebrand + website archaeology (firebase/public/ → apps/website/, src/instrument/) ---
    "docs/release/agentic_dynamics_arxiv_draft.md": frozenset(
        {"src/instrument/", "firebase/public/", "code_reviews/2026-08-14"}
    ),
    "docs/release/agentic_dynamics_rebrand_plan.md": frozenset(
        {"src/instrument/", "firebase/public/"}
    ),
    "docs/verification/agentic_dynamics_rebrand_verify.md": frozenset({"firebase/public/"}),
    "docs/architecture/current/architecture_visual.md": frozenset({"firebase/public/"}),
    "docs/website/facelift.md": frozenset({"firebase/public/"}),
    "docs/website/narrative.md": frozenset({"firebase/public/"}),
    "docs/website/redesign.md": frozenset({"firebase/public/"}),
    "docs/release/remediation_plan.md": frozenset(
        {"src/instrument/", "experiments/configs/", "firebase/public/"}
    ),
    "docs/verification/remediation_verify.md": frozenset({"src/instrument/", "firebase/public/"}),
    "docs/verification/verify_evidence.md": frozenset({"firebase/public/"}),
    "docs/verification/verify_evidence_redesign.md": frozenset({"firebase/public/"}),
    "docs/verification/verify_framework.md": frozenset({"firebase/public/"}),
    # --- opencode docs refresh + Claude Code port (document the admin/server.py mapping) ---
    "docs/website/opencode_docs_challenge.md": frozenset({"src/instrument/"}),
    "docs/website/opencode_docs_scope.md": frozenset(
        {"src/instrument/", "experiments/configs/", "admin/server.py", "code_reviews/2026-08-14"}
    ),
    "docs/website/opencode_docs_spec.md": frozenset(
        {"src/instrument/", "experiments/configs/", "admin/server.py", "code_reviews/2026-08-14"}
    ),
    "docs/architecture/current/claude_code_port.md": frozenset({"admin/server.py"}),
    "docs/architecture/current/claude_tools_to_skills_scope.md": frozenset(
        {"src/instrument/", "experiments/configs/", "admin/server.py"}
    ),
    "docs/verification/claude_tools_to_skills_verify.md": frozenset(
        {"src/instrument/", "experiments/configs/", "admin/server.py"}
    ),
    # --- routing design/survey/verify (predate the package rename + Control Room move) ---
    "docs/architecture/current/routing_design.md": frozenset(
        {"src/instrument/", "admin/server.py", "code_reviews/2026-08-14"}
    ),
    "docs/verification/review_verify.md": frozenset({"admin/server.py"}),
    "docs/verification/routing_follow_up_verify.md": frozenset({"src/instrument/"}),
    "docs/architecture/current/routing_next_steps.md": frozenset({"src/instrument/"}),
    "docs/architecture/current/routing_signal_store_notes.md": frozenset({"src/instrument/"}),
    "docs/verification/routing_survey.md": frozenset(
        {"src/instrument/", "admin/server.py", "firebase/public/", "code_reviews/2026-08-14"}
    ),
    "docs/verification/routing_verify.md": frozenset({"src/instrument/"}),
    # --- spec/scope/challenge/verify (pre-refactor design + verification) ---
    "docs/architecture/current/challenge.md": frozenset({"src/instrument/", "admin/server.py"}),
    "docs/architecture/current/scope.md": frozenset({"src/instrument/", "admin/server.py"}),
    "docs/architecture/current/spec.md": frozenset({"src/instrument/", "admin/server.py"}),
    "docs/verification/verify.md": frozenset({"admin/server.py"}),
    # --- surveys / audits / verifies (analyze the pre-refactor tree) ---
    "docs/verification/auto_posthoc_survey.md": frozenset({"src/instrument/"}),
    "docs/verification/auto_posthoc_verify.md": frozenset({"src/instrument/"}),
    "docs/verification/control_room_survey.md": frozenset({"src/instrument/", "admin/server.py"}),
    "docs/verification/operator_audit.md": frozenset({"src/instrument/"}),
    "docs/verification/operator_fix_verify.md": frozenset({"src/instrument/"}),
    "docs/verification/workflow_phase_survey.md": frozenset(
        {"src/instrument/", "admin/server.py"}
    ),
    "docs/verification/workflow_phase_verify.md": frozenset(
        {"src/instrument/", "admin/server.py"}
    ),
    # --- spec-lifecycle verification (moved from docs/spec_lifecycle/) ---
    "docs/verification/spec_lifecycle_verify.md": frozenset({"src/instrument/"}),
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
    """Every accepted doc (root + ``docs/**``).

    ``docs/designs/current/`` was retired as a path family by the docs-taxonomy restructure;
    its two remaining entries (the in-flight 2d/2f preregistrations) are ``accepted`` and are
    therefore already covered by the accepted-status scan.
    """
    targets: set[Path] = set()
    for path in sorted(ROOT.glob("*.md")) + sorted((ROOT / "docs").rglob("*.md")):
        if _status(path) == "accepted":
            targets.add(path)
    return sorted(targets)


def _agent_config_targets() -> list[Path]:
    """Every file under the neutral ``agent_config/`` source (agents, skills, commands, rules…).

    These are the *active* agent-context files the renderers project into ``.opencode/`` +
    ``.claude/`` — executable context for the systems that modify the repo, so a retired-path
    mention here is the highest-severity staleness (review item 6: "extend the stale-path guard
    to the complete ``agent_config/**`` tree").
    """
    return sorted((ROOT / "agent_config").rglob("*.md"))


def _is_allowed(rel: str, family: str) -> bool:
    """True when ``rel`` (or a directory prefix of it) explicitly allows ``family``."""
    for prefix, allowed in ALLOWLIST.items():
        is_dir_match = prefix.endswith("/") and rel.startswith(prefix)
        is_file_match = not prefix.endswith("/") and rel == prefix
        if (is_dir_match or is_file_match) and ("*" in allowed or family in allowed):
            return True
    return False


def test_accepted_docs_use_no_retired_paths():
    """No accepted doc names a retired path outside the explicit historical allowlist."""
    violations: list[str] = []
    for path in _scan_targets():
        rel = str(path.relative_to(ROOT))
        text = path.read_text(encoding="utf-8")
        for family in RETIRED_PATH_FAMILIES:
            if family in text and not _is_allowed(rel, family):
                violations.append(
                    f"{rel}: {family!r} (retired — repoint or add an allowlist entry)"
                )
    assert not violations, "accepted/current docs referencing retired paths:\n" + "\n".join(
        sorted(violations)
    )


def test_agent_config_uses_no_retired_paths():
    """No ``agent_config/**`` file names a retired path family.

    Unlike the accepted-docs check above, there is **no** allowlist here: the neutral
    agent-context source must never carry a retired path, even in historical framing — the
    semantic guard (``test_agent_config_semantic.py``) independently proves every *referenced*
    path resolves, and this check proves every retired *family* is absent entirely.
    """
    violations: list[str] = []
    for path in _agent_config_targets():
        rel = str(path.relative_to(ROOT))
        text = path.read_text(encoding="utf-8")
        for family in RETIRED_PATH_FAMILIES:
            if family in text:
                violations.append(f"{rel}: {family!r} (retired — repoint to the current path)")
    assert not violations, "agent_config files referencing retired paths:\n" + "\n".join(
        sorted(violations)
    )
    assert not violations, "accepted/current docs referencing retired paths:\n" + "\n".join(
        sorted(violations)
    )


def test_allowlist_entries_all_resolve():
    """Every allowlist key names an existing file (or a non-empty directory prefix)."""
    for prefix in ALLOWLIST:
        if prefix.endswith("/"):
            assert (ROOT / prefix).is_dir(), f"allowlist dir prefix does not exist: {prefix}/"
        else:
            assert (ROOT / prefix).is_file(), f"allowlist file does not exist: {prefix}"
