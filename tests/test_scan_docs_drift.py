"""Tests for the deterministic docs-drift scanner (``scripts/scan_docs_drift.py``).

The scanner's contract has two directions, and the workflow spec's VERIFY demands both:

1. **It does not cry wolf.** On a well-formed claim the scanner reports ``current``. A false drift
   flag is the failure mode that burns operator trust, so the no-false-positive tests here are as
   load-bearing as the detection tests — in particular the two regressions found while building
   the baseline (prose mistaken for a CLI tree; a moved file mistaken for a deleted one).

2. **It catches a seeded break.** Each axis is exercised against a deliberately corrupted fixture
   — a deleted line anchor, a wrong flag, a wrong count, a stripped status, an unclassified
   script — and must produce a finding on the MATCHING check.

Fixtures are built in ``tmp_path`` and the module's ``ROOT`` is monkeypatched at the module level,
so no test mutates the real tree. The scanner is deterministic and makes zero model calls, so
every assertion here is exact rather than statistical.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCANNER_PATH = REPO_ROOT / "scripts" / "scan_docs_drift.py"


def _load_scanner():
    """Import ``scripts/scan_docs_drift.py`` as a module (it is a script, not a package member)."""
    spec = importlib.util.spec_from_file_location("scan_docs_drift", SCANNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Register BEFORE exec: @dataclass resolves `cls.__module__` through sys.modules, so a module
    # executed while unregistered raises AttributeError on the first dataclass it defines.
    sys.modules["scan_docs_drift"] = module
    spec.loader.exec_module(module)
    return module


scanner = _load_scanner()


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Fixture: a miniature repository with well-formed claims
# ─────────────────────────────────────────────────────────────────────────────────────────────


def _write(path: Path, text: str) -> None:
    """Write ``text`` to ``path``, creating parents. Trailing newline normalised."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


@pytest.fixture()
def fake_repo(tmp_path: Path, monkeypatch) -> Path:
    """A minimal git repository whose every scanned claim is CURRENT.

    Built as a real git checkout because three checks shell out to git: the pinned module count
    (``ls-tree`` at a SHA), the report's HEAD, and the anchor basename index (``ls-files``).
    Keeping it a real repo tests the scanner as it actually runs rather than around its seams.
    """
    root = tmp_path / "repo"
    root.mkdir()

    # ── a target script with a known flag surface (both parsing idioms) ─────────────────────
    _write(
        root / "scripts" / "run_workflow.py",
        '''"""Fake runner."""
import argparse, sys

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--spec")
    p.add_argument("--goal")
    p.add_argument("--model")
    p.add_argument("--resume", action="store_true")
    # a hand-rolled flag, to prove the literal extractor covers non-argparse idioms
    verbose = "--legacy-flag" in sys.argv
    return 0
''',
    )
    _write(root / "scripts" / "CONTEXT.md", _manifest(["run_workflow.py"]))

    # ── the fast path (the fast_path axis's referents) ───────────────────────────────────────
    _write(
        root / "scripts" / "test_fast.sh",
        '#!/usr/bin/env bash\n'
        '# The fast-path smoke: the `fast`-marked subset (test_suite_speed p3).\n'
        'set -euo pipefail\n'
        'cd "$(dirname "$0")/.."\n'
        'python3 -m pytest tests/ -m fast -q -p no:cacheprovider "$@"\n',
    )
    _write(
        root / "tests" / "test_fast_path_gate.py",
        '"""The fast-path budget gate (test_suite_speed p4)."""\n'
        "FAST_BUDGET_SECONDS = 180\n",
    )
    _write(
        root / "tests" / "test_dependency_direction.py",
        '"""A pure-unit guard family member."""\n'
        "pytestmark = pytest.mark.fast\n",
    )

    # ── the package planes ───────────────────────────────────────────────────────────────────
    for plane in ("core", "control"):
        _write(root / "src" / "agentic_dynamics" / plane / "__init__.py", '"""plane."""\n')
    _write(root / "src" / "agentic_dynamics" / "__init__.py", '"""pkg."""\n')
    # A faithful miniature of the real dispatcher: the scanner resolves subcommand claims through
    # `_resolve` loaded from the SCANNED tree, so the fixture must supply a real one.
    _write(
        root / "src" / "agentic_dynamics" / "cli.py",
        '''"""Fake dispatcher mirroring the real longest-prefix resolver."""
_COMMANDS = {
    ("workflow", "run"): "run_workflow.py",
    ("spec", "status"): "run_workflow.py",
}
_SORTED_PREFIXES = sorted(_COMMANDS, key=len, reverse=True)

def _resolve(argv):
    for prefix in _SORTED_PREFIXES:
        if tuple(argv[: len(prefix)]) == prefix:
            return _COMMANDS[prefix], argv[len(prefix):]
    return None, []
''',
    )
    # a module with a comfortable line count, used as the anchor target
    _write(
        root / "src" / "agentic_dynamics" / "control" / "facts.py",
        "\n".join(f"# line {i}" for i in range(1, 61)),
    )

    # ── the spec lifecycle index ─────────────────────────────────────────────────────────────
    _write(
        root / "experiments" / "specs" / "index.json",
        json.dumps(
            {
                "specs": [
                    {"name": "e1", "artifact_kind": "experiment"},
                    {"name": "w1", "artifact_kind": "workflow"},
                    {"name": "w2", "artifact_kind": "workflow"},
                ]
            }
        ),
    )

    # ── documents ────────────────────────────────────────────────────────────────────────────
    _write(
        root / "README.md",
        "---\nstatus: accepted\n---\n\n# README\n\n"
        "| Experiment + workflow specs | 3 (1 experiments + 2 workflows) |\n",
    )
    # ARCHITECTURE.md is written WITHOUT the pinned-SHA sentence; the fixture fills it in after
    # the first commit, when a SHA exists to pin to.
    _write(
        root / "ARCHITECTURE.md",
        "---\nstatus: accepted\n---\n\n# ARCHITECTURE\n\n"
        "| Plane | Ownership |\n|---|---|\n"
        "| `core` | foundation |\n"
        "| `control` | control plane |\n\n"
        "The fact store lives at `src/agentic_dynamics/control/facts.py:42`.\n"
        "PINNED_CLAIM_GOES_HERE\n",
    )
    _write(
        root / "agent_config" / "mental-model.md",
        "# mental model\n\n"
        "Prose that merely mentions `agentic-dynamics docs scan` and describes how it "
        "regenerates every derived surface from its sources must NOT be read as a command tree.\n"
        "\n```\n"
        "agentic-dynamics\n"
        "├─ workflow    run\n"
        "└─ spec        status\n"
        "```\n"
        "\n```\n"
        "  # full CLI: scripts/run_workflow.py --spec/--goal/--model [--resume]\n"
        "```\n",
    )
    _write(
        root / "docs" / "architecture" / "current" / "design.md",
        "---\nstatus: accepted\n---\n\n# design\n\n"
        "See `src/agentic_dynamics/control/facts.py:50` and `facts.py:12`.\n",
    )

    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()

    # Now the pinned claim can name a real SHA. Three nested modules exist at that commit
    # (core/__init__, control/__init__, control/facts) — the plane-root __init__/cli are excluded
    # by the doc's own `**/*.py` basis, exactly as in the real repository.
    arch = root / "ARCHITECTURE.md"
    arch.write_text(
        arch.read_text(encoding="utf-8").replace(
            "PINNED_CLAIM_GOES_HERE",
            f"[C] 3 tracked Python modules at the pinned SHA `{sha}`",
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "commit", "-qam", "pin"], cwd=root, check=True)

    monkeypatch.setattr(scanner, "ROOT", root)
    monkeypatch.setattr(scanner, "_BASENAME_INDEX", None)  # cache is per-tree
    # The fixture's docs use the real repo's kind-tree names, but only `docs/architecture/current`
    # exists here; restrict the kind-tree rule so absent trees are not reported as scan errors.
    monkeypatch.setattr(
        scanner, "KIND_TREE_STATUS", {"docs/architecture/current": "accepted"}
    )
    # The fixture documents one surface (its own mental-model.md) against its own runner.
    monkeypatch.setattr(
        scanner,
        "DOCUMENTED_CLI_SURFACES",
        (
            {
                "id": "fixture_full_cli",
                "doc": "agent_config/mental-model.md",
                "target": "scripts/run_workflow.py",
                "mode": "marker_block",
                "marker": "full CLI: scripts/run_workflow.py",
                "complete": True,
            },
        ),
    )
    monkeypatch.setattr(scanner, "DOCUMENTED_CLI_TREES", ("agent_config/mental-model.md",))
    monkeypatch.setattr(scanner, "CURRENT_INVENTORY_DOCS", ("README.md", "ARCHITECTURE.md"))
    return root


def _manifest(names: list[str]) -> str:
    """A scripts/CONTEXT.md carrying a well-formed classification manifest + the fast-path section.

    The fixture is written BEFORE the fast-path files are added, so the ``fast_path`` axis's
    claims have a referent at scan time (the clean-fixture control demands zero drift).
    """
    return (
        "# scripts\n\n"
        "<!-- scripts-classification: start -->\n"
        f"maintained: {' '.join(names)}\n"
        "historical:\n"
        "one-time:\n"
        "fleet:\n"
        "<!-- scripts-classification: end -->\n\n"
        "**The fast path** — `bash scripts/test_fast.sh`: the `fast`-marked subset (the "
        "sub-minute guards + the audited pure-unit families). Target: sub-3-minutes. "
        "**Budget gate** — `tests/test_fast_path_gate.py`: the fast path must stay under "
        "budget 180s, and the fast path must be a subset of the suite (never a new parallel "
        "suite).\n"
    )


def _run(axes=None):
    """Run the scan and return ``(report, findings_by_axis)``."""
    report = scanner.scan(axes or scanner.AXES)
    by_axis: dict[str, list] = {}
    for finding in report.findings:
        by_axis.setdefault(finding.axis, []).append(finding)
    return report, by_axis


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Direction 1 — the scanner does not cry wolf
# ─────────────────────────────────────────────────────────────────────────────────────────────


def test_clean_fixture_reports_zero_drift(fake_repo):
    """A tree whose every claim is well-formed scores exactly zero, with no axis errored.

    This is the control for every detection test below: without it, a seeded break "producing a
    finding" would prove nothing, since a scanner that flags everything also flags the break.
    """
    report, by_axis = _run()
    assert report.errors == {}, f"axes failed to run: {report.errors}"
    assert report.score()["drift"] == 0, (
        "clean fixture produced findings:\n"
        + "\n".join(f"  {f.axis} {f.status} {f.source}: {f.code_truth}" for f in report.findings)
    )
    # Every axis must have actually checked something — a vacuous axis silently scores zero.
    for axis in scanner.AXES:
        assert report.score()["per_axis"][axis]["checked"] > 0, f"{axis} checked nothing"


def test_prose_mentioning_a_command_is_not_read_as_a_cli_tree(fake_repo):
    """Regression: prose outside a code fence must not be parsed into phantom subcommands.

    The fixture's mental-model.md contains the sentence "…`agentic-dynamics docs scan` … how it
    regenerates every derived surface from its sources". A fence-blind scan split that into the
    verbs ``regenerates``/``every``/``derived``/``from``/``its`` and reported five phantom
    subcommands — six such false positives appeared in the first real baseline run.
    """
    _, by_axis = _run(("cli_surface",))
    assert not by_axis.get("cli_surface"), (
        "prose was parsed as command claims: "
        + str([f.claim for f in by_axis.get("cli_surface", [])])
    )


def test_moved_file_is_resolved_not_reported_missing(fake_repo):
    """Regression: an anchor whose file MOVED must resolve by basename, not report ``missing``.

    ``docs/architecture/current/design.md`` cites the bare name ``facts.py:12``. The file lives at
    ``src/agentic_dynamics/control/facts.py``. Reporting that as a missing file would be a false
    alarm about a claim a reader can trivially follow.
    """
    _, by_axis = _run(("anchor_integrity",))
    assert not by_axis.get("anchor_integrity")


def test_generated_artifacts_cannot_mask_a_dangling_anchor(fake_repo):
    """A dangling anchor must NOT be rescued by a same-named agent-generated artifact.

    False-NEGATIVE guard. ``experiments/results/artifacts/`` holds captured story outputs full of
    ordinary names — the real tree has seven ``server.py`` files there, beside the
    ``admin/server.py:1365`` anchor that genuinely dangles. If the basename fallback indexed them,
    one long enough artifact would silently mark a broken anchor ``current`` and the finding would
    vanish. Here ``facts.py`` is truncated to 5 lines while a 500-line namesake is planted under
    the excluded tree; the anchor must still be reported.
    """
    target = fake_repo / "src" / "agentic_dynamics" / "control" / "facts.py"
    target.write_text("\n".join(f"# line {i}" for i in range(1, 6)), encoding="utf-8")
    _write(
        fake_repo / "experiments" / "results" / "artifacts" / "deadbeef" / "facts.py",
        "\n".join(f"# decoy {i}" for i in range(1, 501)),
    )
    subprocess.run(["git", "add", "-A"], cwd=fake_repo, check=True)
    subprocess.run(["git", "commit", "-qm", "decoy"], cwd=fake_repo, check=True)
    scanner._BASENAME_INDEX = None  # rebuild the index over the new tree

    _, by_axis = _run(("anchor_integrity",))
    findings = by_axis.get("anchor_integrity", [])
    assert findings, "a generated artifact masked a genuinely dangling anchor"
    assert all(f.status == "stale" for f in findings)


def test_pinned_claim_is_verified_at_its_pin_not_at_head(fake_repo):
    """The load-bearing semantic: a SHA-pinned count is checked AT THAT SHA.

    A new module is added at HEAD, so the tree now holds 4 nested modules while the doc claims 3
    "at the pinned SHA". The claim is still true *at its anchor*, so it must stay ``current`` —
    a scanner comparing it to HEAD would flag a correctly-written claim.
    """
    _write(
        fake_repo / "src" / "agentic_dynamics" / "control" / "newly_added.py", '"""new."""\n'
    )
    subprocess.run(["git", "add", "-A"], cwd=fake_repo, check=True)
    subprocess.run(["git", "commit", "-qm", "add module"], cwd=fake_repo, check=True)

    report, by_axis = _run(("module_inventory",))
    assert not by_axis.get("module_inventory"), (
        "a SHA-pinned claim was judged against HEAD: "
        + str([f.code_truth for f in by_axis.get("module_inventory", [])])
    )


def test_historical_documents_are_out_of_count_scope(fake_repo):
    """A point-in-time record quoting an old count is not drift.

    Review and handoff documents quote historical counts as evidence (the real
    ``cap_stabilization_release_adversary.md`` quotes the very mismatch it filed). Flagging them
    would pressure an author into rewriting the record to match today's tree.
    """
    _write(
        fake_repo / "docs" / "reviews" / "old_review.md",
        "---\nstatus: accepted\n---\n\n"
        "At the time, the README reported 99 (1 experiments + 98 workflows).\n",
    )
    _, by_axis = _run(("spec_lifecycle",))
    assert not by_axis.get("spec_lifecycle")


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Direction 2 — seeded breaks are caught by the MATCHING check
# ─────────────────────────────────────────────────────────────────────────────────────────────


def test_seeded_deleted_line_anchor_is_caught(fake_repo):
    """(e) Truncating a file so a cited line no longer exists produces a ``stale`` anchor finding.

    This is the spec's named seeded break: "a deleted line anchor". ``design.md`` cites
    ``facts.py:50``; the file is cut to 20 lines.
    """
    target = fake_repo / "src" / "agentic_dynamics" / "control" / "facts.py"
    target.write_text("\n".join(f"# line {i}" for i in range(1, 21)), encoding="utf-8")

    _, by_axis = _run(("anchor_integrity",))
    findings = by_axis.get("anchor_integrity", [])
    assert findings, "a truncated file left its dangling anchors undetected"
    assert all(f.status == "stale" for f in findings), [f.status for f in findings]
    assert any(":50" in f.claim for f in findings), [f.claim for f in findings]
    # The finding must carry a re-derivable basis — the anchored-claim discipline.
    assert all("wc -l" in f.basis for f in findings)


def test_seeded_wrong_flag_is_caught(fake_repo):
    """(a) A documented flag that argparse does not declare produces a ``stale`` CLI finding.

    The spec's second named seeded break: "a wrong flag".
    """
    doc = fake_repo / "agent_config" / "mental-model.md"
    doc.write_text(
        doc.read_text(encoding="utf-8").replace("--resume]", "--resume --not-a-real-flag]"),
        encoding="utf-8",
    )
    _, by_axis = _run(("cli_surface",))
    findings = by_axis.get("cli_surface", [])
    assert any(
        f.status == "stale" and "--not-a-real-flag" in f.check_id for f in findings
    ), [f.check_id for f in findings]


def test_seeded_undocumented_flag_is_caught_only_when_completeness_is_claimed(fake_repo):
    """(a) A new code flag is ``missing`` from a doc that claims the FULL CLI — but not otherwise.

    Both halves matter: the reverse direction must fire for a completeness-claiming surface, and
    must stay silent for a partial reference block, which is entitled to summarise.
    """
    script = fake_repo / "scripts" / "run_workflow.py"
    script.write_text(
        script.read_text(encoding="utf-8").replace(
            'p.add_argument("--resume", action="store_true")',
            'p.add_argument("--resume", action="store_true")\n    p.add_argument("--brand-new")',
        ),
        encoding="utf-8",
    )

    _, by_axis = _run(("cli_surface",))
    assert any(
        f.status == "missing" and "--brand-new" in f.check_id
        for f in by_axis.get("cli_surface", [])
    ), "a completeness-claiming doc did not report the undocumented flag"

    # Same tree, same new flag — but the surface no longer claims completeness.
    partial = dict(scanner.DOCUMENTED_CLI_SURFACES[0])
    partial["complete"] = False
    scanner.DOCUMENTED_CLI_SURFACES = (partial,)
    _, by_axis_partial = _run(("cli_surface",))
    assert not by_axis_partial.get("cli_surface"), (
        "a partial reference block was penalised for not enumerating every flag"
    )


def test_seeded_unresolvable_subcommand_is_caught(fake_repo):
    """(a) A documented ``agentic-dynamics`` verb that the dispatcher cannot resolve is stale."""
    doc = fake_repo / "agent_config" / "mental-model.md"
    doc.write_text(
        doc.read_text(encoding="utf-8").replace("└─ spec        status", "└─ spec        ghostverb"),
        encoding="utf-8",
    )
    _, by_axis = _run(("cli_surface",))
    assert any(
        f.status == "stale" and "ghostverb" in f.check_id for f in by_axis.get("cli_surface", [])
    ), [f.check_id for f in by_axis.get("cli_surface", [])]


def test_seeded_wrong_module_count_is_caught(fake_repo):
    """(b) A pinned count that disagrees with the tree AT ITS PIN is stale."""
    arch = fake_repo / "ARCHITECTURE.md"
    arch.write_text(
        arch.read_text(encoding="utf-8").replace(
            "3 tracked Python modules", "999 tracked Python modules"
        ),
        encoding="utf-8",
    )
    _, by_axis = _run(("module_inventory",))
    findings = by_axis.get("module_inventory", [])
    assert any(f.status == "stale" and "pinned_module_count" in f.check_id for f in findings)


def test_seeded_unresolvable_pinned_sha_is_missing_not_stale(fake_repo):
    """(b) A pin that no longer resolves is ``missing`` — a different defect from a wrong count.

    The distinction is what makes the score actionable: a wrong number is edited, a vanished SHA
    means the anchor itself must be re-pinned.
    """
    arch = fake_repo / "ARCHITECTURE.md"
    text = arch.read_text(encoding="utf-8")
    import re as _re

    text = _re.sub(r"pinned SHA `[0-9a-f]+`", "pinned SHA `" + "d" * 40 + "`", text)
    arch.write_text(text, encoding="utf-8")

    report, by_axis = _run(("module_inventory",))
    assert any(
        f.status == "missing" and "pinned_module_count" in f.check_id
        for f in by_axis.get("module_inventory", [])
    )


def test_seeded_wrong_spec_count_is_caught(fake_repo):
    """(c) A current-authority doc whose spec count disagrees with index.json is stale."""
    readme = fake_repo / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace(
            "3 (1 experiments + 2 workflows)", "7 (1 experiments + 6 workflows)"
        ),
        encoding="utf-8",
    )
    _, by_axis = _run(("spec_lifecycle",))
    findings = by_axis.get("spec_lifecycle", [])
    assert findings and all(f.status == "stale" for f in findings)
    assert "index.json holds 3" in findings[0].code_truth


def test_seeded_missing_status_frontmatter_is_caught(fake_repo):
    """(d) A doc with no lifecycle status frontmatter is ``missing`` (doc-lifecycle guard mirror)."""
    _write(fake_repo / "docs" / "stray.md", "# no frontmatter here\n")
    _, by_axis = _run(("status_vocabulary",))
    assert any(
        f.status == "missing" and "stray.md" in f.check_id
        for f in by_axis.get("status_vocabulary", [])
    )


def test_seeded_status_outside_vocabulary_is_caught(fake_repo):
    """(d) A status outside the enforced vocabulary is ``stale``, not merely absent."""
    _write(fake_repo / "docs" / "odd.md", "---\nstatus: vibes\n---\n\n# odd\n")
    _, by_axis = _run(("status_vocabulary",))
    assert any(
        f.status == "stale" and "odd.md" in f.check_id
        for f in by_axis.get("status_vocabulary", [])
    )


def test_seeded_kind_tree_status_violation_is_caught(fake_repo):
    """(d) ``docs/architecture/current/`` entries must be ``accepted``."""
    doc = fake_repo / "docs" / "architecture" / "current" / "design.md"
    doc.write_text(
        doc.read_text(encoding="utf-8").replace("status: accepted", "status: proposed"),
        encoding="utf-8",
    )
    _, by_axis = _run(("status_vocabulary",))
    assert any(
        f.status == "stale" and "kind_tree" in f.check_id
        for f in by_axis.get("status_vocabulary", [])
    )


def test_seeded_manifest_orphan_is_caught(fake_repo):
    """(f) A script on disk in no manifest bucket is ``missing`` (script-classification mirror)."""
    _write(fake_repo / "scripts" / "brand_new_tool.py", '"""new."""\n')
    _, by_axis = _run(("manifest_counts",))
    assert any(
        f.status == "missing" and "brand_new_tool.py" in f.check_id
        for f in by_axis.get("manifest_counts", [])
    )


def test_seeded_manifest_phantom_is_caught(fake_repo):
    """(f) A manifest entry with no script on disk is ``stale`` — the manifest over-reports."""
    _write(fake_repo / "scripts" / "CONTEXT.md", _manifest(["run_workflow.py", "deleted_tool.py"]))
    _, by_axis = _run(("manifest_counts",))
    assert any(
        f.status == "stale" and "phantom/deleted_tool.py" in f.check_id
        for f in by_axis.get("manifest_counts", [])
    )


def test_seeded_double_classified_script_is_caught(fake_repo):
    """(f) A script in two buckets falsifies the "exactly one bucket" claim."""
    _write(
        fake_repo / "scripts" / "CONTEXT.md",
        "# scripts\n\n<!-- scripts-classification: start -->\n"
        "maintained: run_workflow.py\n"
        "historical: run_workflow.py\n"
        "one-time:\nfleet:\n"
        "<!-- scripts-classification: end -->\n",
    )
    _, by_axis = _run(("manifest_counts",))
    assert any(
        "double/run_workflow.py" in f.check_id for f in by_axis.get("manifest_counts", [])
    )


def test_seeded_fast_path_budget_drift_is_caught(fake_repo):
    """(g) A CONTEXT.md budget that disagrees with the gate's constant is ``stale``.

    The fast-path budget is the rail's live claim: the doc says "under 180s", the gate enforces
    ``FAST_BUDGET_SECONDS = 180``. A doc that drifts from the gate is exactly the stale-claim
    class this axis exists to catch.
    """
    context = fake_repo / "scripts" / "CONTEXT.md"
    context.write_text(
        context.read_text(encoding="utf-8").replace("180s", "999s"),
        encoding="utf-8",
    )
    report, by_axis = _run(("fast_path",))
    assert report.errors == {}
    assert any(
        f.status == "stale" and "budget" in f.check_id
        for f in by_axis.get("fast_path", [])
    )


def test_seeded_fast_path_command_removed_is_caught(fake_repo):
    """(g) A missing fast-path command is ``missing`` — the doc names a script that is gone."""
    (fake_repo / "scripts" / "test_fast.sh").unlink()
    report, by_axis = _run(("fast_path",))
    assert report.errors == {}
    assert any(
        f.status == "missing" and "command" in f.check_id
        for f in by_axis.get("fast_path", [])
    )


def test_seeded_fast_path_empty_subset_is_caught(fake_repo):
    """(g) A fast subset with no marked module is ``stale`` — the marker set silently emptied."""
    (fake_repo / "tests" / "test_dependency_direction.py").write_text(
        '"""A pure-unit guard family member."""\n',
        encoding="utf-8",
    )
    report, by_axis = _run(("fast_path",))
    assert report.errors == {}
    assert any(
        f.status == "stale" and "subset" in f.check_id
        for f in by_axis.get("fast_path", [])
    )


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Report contract — the shape the watchdog (p2), the gate (p3) and the portal (p4) consume
# ─────────────────────────────────────────────────────────────────────────────────────────────


def test_report_json_carries_score_basis_and_schema(fake_repo):
    """Every finding is re-derivable and the score breaks down per axis."""
    target = fake_repo / "src" / "agentic_dynamics" / "control" / "facts.py"
    target.write_text("# only one line", encoding="utf-8")
    report, _ = _run()
    payload = report.to_json()

    assert payload["schema"] == "docs-drift/v1"
    score = payload["score"]
    assert score["drift"] == score["total_stale"] + score["total_missing"]
    assert set(score["per_axis"]) >= set(scanner.AXES)
    assert score["per_axis"]["anchor_integrity"]["drift"] > 0
    assert payload["findings"], "expected findings to be serialised"
    for finding in payload["findings"]:
        # Hard rule 4: a finding without a reproducible basis is prose, not a finding.
        assert finding["basis"].strip(), finding
        assert finding["status"] in {"stale", "missing"}
        assert finding["claim"] and finding["code_truth"]
    # Default serialisation carries findings only; the full inventory is opt-in.
    assert payload["includes_current_rows"] is False
    assert report.to_json(include_current=True)["includes_current_rows"] is True


def test_errored_axis_is_reported_not_scored_clean(fake_repo):
    """An axis that cannot run is recorded in ``errors`` — never silently counted as clean."""
    (fake_repo / "scripts" / "CONTEXT.md").write_text("no markers here\n", encoding="utf-8")
    report, _ = _run(("manifest_counts",))
    assert "manifest_counts" in report.errors
    assert "markers" in report.errors["manifest_counts"]


def test_unmeasurable_scan_exits_2_not_0(fake_repo):
    """An incomplete scan exits 2 — distinguishable from clean (0) and drift found (1).

    A partial scan reporting "drift 0" is the most dangerous output this tool can produce: it
    reads exactly like a clean tree. Exit 2 fires whether or not ``--fail-on-drift`` was passed,
    because "I could not measure" is never a pass.
    """
    assert scanner.main(["--quiet"]) == 0, "the clean fixture should exit 0"

    # Break scripts/CONTEXT.md so its axes cannot run; the tree is otherwise unchanged and
    # drift-free. The manifest axis errors on the missing markers; the fast_path axis errors on
    # the missing fast-path section (the same source doc — neither can measure, neither is
    # scored clean).
    (fake_repo / "scripts" / "CONTEXT.md").write_text("no markers here\n", encoding="utf-8")
    report, _ = _run()
    assert report.errors, "expected the CONTEXT.md-driven axes to error"
    assert report.score()["drift"] == 0, "an errored axis must not inflate the drift score"
    assert report.score()["axes_errored"] == ["fast_path", "manifest_counts"]

    # Exit 2 regardless of --fail-on-drift: an unmeasured axis is never reported as a pass.
    assert scanner.main(["--quiet"]) == 2
    assert scanner.main(["--quiet", "--fail-on-drift"]) == 2


def test_scan_makes_zero_model_calls(fake_repo):
    """Hard rule 1: the scanner's only subprocess is ``git``.

    Asserted structurally by intercepting ``subprocess.run`` — any non-git command (an LLM CLI,
    a network fetch) fails the test loudly rather than being caught by code review.
    """
    seen: list[list[str]] = []
    real_run = subprocess.run

    def _guard(cmd, *a, **kw):
        seen.append(list(cmd))
        return real_run(cmd, *a, **kw)

    import scan_docs_drift as _mod  # noqa: F401  (module object is `scanner`)

    orig = scanner.subprocess.run
    scanner.subprocess.run = _guard
    try:
        scanner.scan(scanner.AXES)
    finally:
        scanner.subprocess.run = orig

    assert seen, "expected at least one git invocation"
    for cmd in seen:
        assert cmd[0] == "git", f"non-git subprocess in a deterministic scan: {cmd}"
        assert cmd[1] in {"rev-parse", "ls-files", "ls-tree"}, f"non-read-only git: {cmd}"


# ─────────────────────────────────────────────────────────────────────────────────────────────
# The real tree — the scanner runs, and its exit contract holds
# ─────────────────────────────────────────────────────────────────────────────────────────────


def test_scanner_runs_on_the_real_repository():
    """The scanner completes on the real tree with no axis errored, and writes a valid report.

    This asserts the scan is OPERABLE and its axes are non-vacuous. It deliberately does NOT
    assert a zero score: the baseline is a measurement, and pinning it here would make an honest
    finding fail the build instead of reaching the p3 proposal gate (spec hard rule 2 — drift is
    a finding, not a verdict).
    """
    if not shutil.which("git"):
        pytest.skip("git unavailable")
    report = scanner.scan(scanner.AXES)
    assert report.errors == {}, f"axes errored on the real tree: {report.errors}"
    for axis in scanner.AXES:
        assert report.score()["per_axis"][axis]["checked"] > 0, f"{axis} is vacuous"
    payload = report.to_json()
    json.dumps(payload)  # must be serialisable


def test_cli_exit_codes(tmp_path):
    """``--fail-on-drift`` exits 1 on a non-zero score; a plain run exits 0."""
    out = tmp_path / "report.json"
    rc = subprocess.run(
        [sys.executable, str(SCANNER_PATH), "--json", str(out), "--quiet"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).returncode
    assert rc == 0, "a plain scan must exit 0 regardless of score"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema"] == "docs-drift/v1"

    result = subprocess.run(
        [sys.executable, str(SCANNER_PATH), "--fail-on-drift", "--quiet"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    expected = 1 if payload["score"]["drift"] > 0 else 0
    assert result.returncode == expected


def test_single_axis_selection_runs_only_that_axis():
    """``--check <axis>`` restricts the scan — the watchdog reruns one axis cheaply."""
    report = scanner.scan(("manifest_counts",))
    assert {c.axis for c in report.checks} == {"manifest_counts"}
