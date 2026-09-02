"""Pre-existing-drift guard (``control_db_evidence`` e5) — "pre-existing" must be PROVEN.

The mislabeling pattern this suite pins: an author whose branch breaks a harness test calls the
failure "pre-existing drift" to wave it away — the exact ``control_db_followups`` f4/f5 move on
2026-09-02, where ``tests/test_doc_lifecycle.py::test_readme_spec_counts_match_index`` was called
"the known pre-existing f0 drift" yet PASSED at the merge base ``ec3eb1c13`` (README 178 / index
178 in sync) — a branch-introduced failure mislabeled as pre-existing. The guard
(:mod:`agentic_dynamics.runtime.preexisting_guard`) proves a failure exists at the base BEFORE
the label is allowed: it resolves the base sha, checks it out in a temp git worktree, runs the
SAME pytest node there, and compares base vs head outcomes. Deterministic, single-test, zero
model calls.

Tests prove both directions (a)-(d) from the e5 mandate:
(a) the guard PASSES when the failure genuinely exists at the merge-base (synthetic: a test
    that fails at base AND on the branch) → verdict ``pre-existing``;
(b) the guard FAILS when the failure is branch-introduced (synthetic: a test that PASSES at
    base, fails on the branch) → verdict ``branch-introduced`` — the mislabel is caught
    mechanically;
(c) the guard runs without model calls — deterministic, sub-minute;
(d) a review doc citing the guard's evidence is accepted; one claiming "pre-existing" without
    it is flagged.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from agentic_dynamics.runtime import preexisting_guard as pg
from agentic_dynamics.runtime.preexisting_guard import GuardError

ROOT = Path(__file__).resolve().parent.parent


# ── synthetic git-repo plumbing (mirrors the test_workflow_runner idiom) ───────────────────


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"
    return proc.stdout.strip()


def _git_init(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "guard@test")
    _git(repo, "config", "user.name", "guard")


def _write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _commit_all(repo: Path, subject: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", subject)
    return _git(repo, "rev-parse", "HEAD")


PASSING_TEST = "def test_thing():\n    assert True\n"
FAILING_TEST = "def test_thing():\n    assert False\n"
# A second, independent passing test so a repo can carry a failing node AND a green one.
UNRELATED_PASSING_TEST = "def test_other():\n    assert True\n"


@pytest.fixture()
def repo_base_fails_branch_fails(tmp_path):
    """Synthetic (a): the test FAILS at base and FAILS on the branch — genuinely pre-existing.

    Base commit introduces a failing test plus a passing one; the branch adds a new module but
    leaves the failing test broken (the branch did not cause this failure).
    """
    repo = tmp_path / "pre_a"
    _git_init(repo)
    _write(repo, "tests/test_thing.py", FAILING_TEST + UNRELATED_PASSING_TEST)
    _write(repo, "pkg.py", "VALUE = 1\n")
    base = _commit_all(repo, "base: failing test present")
    _write(repo, "pkg2.py", "VALUE2 = 2\n")
    head = _commit_all(repo, "branch: unrelated addition, test still fails")
    return {"repo": repo, "base": base, "head": head}


@pytest.fixture()
def repo_base_passes_branch_fails(tmp_path):
    """Synthetic (b): the test PASSES at base and FAILS on the branch — branch-introduced.

    Base commit has a passing test; the branch flips its assertion (the f4/f5 shape: the
    harness test reddens only after the branch's own change).
    """
    repo = tmp_path / "pre_b"
    _git_init(repo)
    _write(repo, "tests/test_thing.py", PASSING_TEST)
    base = _commit_all(repo, "base: test passes")
    _write(repo, "tests/test_thing.py", FAILING_TEST)
    head = _commit_all(repo, "branch: broke the test")
    return {"repo": repo, "base": base, "head": head}


@pytest.fixture()
def repo_test_absent_at_base(tmp_path):
    """Synthetic edge: the failing test did not EXIST at base — a new test cannot pre-exist."""
    repo = tmp_path / "pre_c"
    _git_init(repo)
    _write(repo, "pkg.py", "VALUE = 1\n")
    base = _commit_all(repo, "base: no tests dir")
    _write(repo, "tests/test_thing.py", FAILING_TEST)
    head = _commit_all(repo, "branch: added the failing test")
    return {"repo": repo, "base": base, "head": head}


def _prove(fixture: dict, *, head: str = "HEAD") -> pg.PreexistingEvidence:
    return pg.prove_preexisting(
        fixture["repo"], "tests/test_thing.py::test_thing", fixture["base"], head=head
    )


# ── (a) the guard PASSES when the failure genuinely exists at the merge-base ───────────────


def test_guard_passes_when_failure_exists_at_base(repo_base_fails_branch_fails):
    ev = _prove(repo_base_fails_branch_fails)
    assert ev.verdict == pg.VERDICT_PRE_EXISTING
    assert ev.base_outcome == pg.OUTCOME_FAIL
    assert ev.head_outcome == pg.OUTCOME_FAIL
    assert ev.base_sha == repo_base_fails_branch_fails["base"]
    # The machine citation a review doc must embed is well-formed and self-describing.
    parsed = pg.PreexistingEvidence.from_citation(ev.citation())
    assert parsed is not None
    assert parsed.verdict == pg.VERDICT_PRE_EXISTING
    assert parsed.base_sha == ev.base_sha
    assert parsed.test == "tests/test_thing.py::test_thing"


def test_guard_explicit_head_matches_default_head(repo_base_fails_branch_fails):
    """Passing head explicitly as the branch tip gives the same verdict as HEAD."""
    ev_head = _prove(repo_base_fails_branch_fails, head=repo_base_fails_branch_fails["head"])
    assert ev_head.verdict == pg.VERDICT_PRE_EXISTING


# ── (b) the guard FAILS when the failure is branch-introduced (the mislabel is caught) ──────


def test_guard_fails_when_failure_is_branch_introduced(repo_base_passes_branch_fails):
    ev = _prove(repo_base_passes_branch_fails)
    assert ev.verdict == pg.VERDICT_BRANCH_INTRODUCED
    assert ev.base_outcome == pg.OUTCOME_PASS
    assert ev.head_outcome == pg.OUTCOME_FAIL


def test_guard_fails_when_failing_test_is_absent_at_base(repo_test_absent_at_base):
    """A failing test that did not exist at the merge-base is branch-introduced by definition."""
    ev = _prove(repo_test_absent_at_base)
    assert ev.verdict == pg.VERDICT_BRANCH_INTRODUCED
    assert ev.base_outcome == pg.OUTCOME_ABSENT
    assert ev.head_outcome == pg.OUTCOME_FAIL


# ── (c) deterministic, sub-minute, no model calls ──────────────────────────────────────────


def test_guard_is_deterministic_and_sub_minute(repo_base_passes_branch_fails):
    start = time.monotonic()
    ev1 = _prove(repo_base_passes_branch_fails)
    ev2 = _prove(repo_base_passes_branch_fails)
    elapsed = time.monotonic() - start
    # Same inputs → same evidence record (deterministic), regardless of temp worktree identity.
    assert ev1.to_dict() == ev2.to_dict()
    assert elapsed < 60, f"guard took {elapsed:.1f}s — expected sub-minute"
    assert ev1.verdict == pg.VERDICT_BRANCH_INTRODUCED


def test_guard_module_performs_no_model_calls():
    """The guard's import graph must stay model-free (no adapters/control/agent invocation).

    A guard that needed an LLM could not be a deterministic, fast, hermetic check — and an
    adversarial reviewer (e6) will look exactly here for a sneaky model dependency.
    """
    import ast
    import importlib

    mod = importlib.import_module("agentic_dynamics.runtime.preexisting_guard")
    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
    forbidden = {
        "agentic_dynamics.adapters",
        "agentic_dynamics.control",
        "agentic_dynamics.knowledge",
    }
    assert not (imported & forbidden), (
        f"guard imports a model-capable module: {imported & forbidden}"
    )
    # The heavy runtime adapter that would call a model is never touched.
    assert "opencode" not in {m.split(".")[-1] for m in imported}
    # The guard's only package dependency is the deterministic pytest runner (test_runner),
    # which is itself model-free — never an adapter, never the knowledge plane.
    pkg_imports = {m for m in imported if m and m.startswith("agentic_dynamics.")}
    assert pkg_imports <= {"agentic_dynamics.runtime.test_runner"}, pkg_imports


# ── (d) review-doc citation requirement: cited = accepted, uncited = flagged ───────────────

GOOD_DOC = """\
# adversarial review

| F1 | test_readme_spec_counts_match_index is pre-existing drift | the f7 gate is red |
"""
BAD_DOC = """\
# adversarial review

The failure is pre-existing drift (test_readme_spec_counts_match_index).
"""


def test_review_doc_citing_guard_evidence_is_accepted():
    evidence = pg.PreexistingEvidence(
        base_sha="a" * 40,
        head_sha="b" * 40,
        test="tests/test_doc_lifecycle.py::test_readme_spec_counts_match_index",
        base_outcome=pg.OUTCOME_FAIL,
        head_outcome=pg.OUTCOME_FAIL,
        verdict=pg.VERDICT_PRE_EXISTING,
    )
    doc = GOOD_DOC + "\n" + evidence.citation() + "\n"
    assert pg.flag_uncited_preexisting_claims(doc) == []


def test_review_doc_claiming_preexisting_without_evidence_is_flagged():
    flagged = pg.flag_uncited_preexisting_claims(BAD_DOC)
    assert len(flagged) == 1
    assert "pre-existing drift" in flagged[0]


def test_review_doc_without_any_claim_is_accepted():
    assert pg.flag_uncited_preexisting_claims("no claims here\n") == []


def test_negated_preexisting_mention_is_not_flagged():
    """'NOT pre-existing' is the correction, not the mislabel — it must never be flagged."""
    assert (
        pg.flag_uncited_preexisting_claims(
            "drift introduced by this wave, not pre-existing drift\n"
        )
        == []
    )


def test_branch_introduced_citation_does_not_satisfy_a_preexisting_claim():
    """A citation whose verdict is branch-introduced proves the OPPOSITE — it must not license
    a 'pre-existing' claim in the same doc (a claim + a contradicting citation is a finding)."""
    contradiction = pg.PreexistingEvidence(
        base_sha="a" * 40,
        head_sha="b" * 40,
        test="tests/test_doc_lifecycle.py::test_readme_spec_counts_match_index",
        base_outcome=pg.OUTCOME_PASS,
        head_outcome=pg.OUTCOME_FAIL,
        verdict=pg.VERDICT_BRANCH_INTRODUCED,
    )
    doc = GOOD_DOC + "\n" + contradiction.citation() + "\n"
    flagged = pg.flag_uncited_preexisting_claims(doc)
    assert len(flagged) == 1
    lineno, _, text = flagged[0].partition(": ")
    assert lineno.isdigit()
    assert "pre-existing drift" in text
    assert "preexisting-guard-evidence" not in text  # the citation itself is never flagged


# ── the CLI surface (scripts/check_preexisting.py) ─────────────────────────────────────────


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_preexisting.py"), *args],
        capture_output=True,
        text=True,
    )


def test_cli_exit_zero_when_pre_existing(repo_base_fails_branch_fails):
    proc = _cli(
        "--test",
        "tests/test_thing.py::test_thing",
        "--base",
        repo_base_fails_branch_fails["base"],
        "--repo",
        str(repo_base_fails_branch_fails["repo"]),
    )
    assert proc.returncode == 0, proc.stderr
    assert "pre-existing" in proc.stdout
    assert "preexisting-guard-evidence:" in proc.stdout


def test_cli_exit_one_when_branch_introduced(repo_base_passes_branch_fails):
    proc = _cli(
        "--test",
        "tests/test_thing.py::test_thing",
        "--base",
        repo_base_passes_branch_fails["base"],
        "--repo",
        str(repo_base_passes_branch_fails["repo"]),
    )
    assert proc.returncode == 1, proc.stderr
    assert "branch-introduced" in proc.stdout


def test_cli_json_carries_the_schema(repo_base_passes_branch_fails, tmp_path):
    import json

    proc = _cli(
        "--json",
        "--test",
        "tests/test_thing.py::test_thing",
        "--base",
        repo_base_passes_branch_fails["base"],
        "--repo",
        str(repo_base_passes_branch_fails["repo"]),
    )
    assert proc.returncode == 1
    doc = json.loads(proc.stdout)
    assert doc["schema"] == "preexisting-guard/v1"
    assert doc["verdict"] == pg.VERDICT_BRANCH_INTRODUCED


def test_cli_doc_mode_accepts_cited_and_flags_uncited(tmp_path):
    evidence = pg.PreexistingEvidence(
        base_sha="a" * 40,
        head_sha="b" * 40,
        test="tests/test_doc_lifecycle.py::test_readme_spec_counts_match_index",
        base_outcome=pg.OUTCOME_FAIL,
        head_outcome=pg.OUTCOME_FAIL,
        verdict=pg.VERDICT_PRE_EXISTING,
    )
    good = tmp_path / "good.md"
    good.write_text(GOOD_DOC + "\n" + evidence.citation() + "\n")
    proc_good = _cli("--doc", str(good))
    assert proc_good.returncode == 0, proc_good.stderr

    bad = tmp_path / "bad.md"
    bad.write_text(BAD_DOC)
    proc_bad = _cli("--doc", str(bad))
    assert proc_bad.returncode == 1
    assert "pre-existing drift" in proc_bad.stdout


def test_cli_usage_error_without_test_or_base(tmp_path):
    repo = tmp_path / "plain"
    repo.mkdir()
    proc = _cli("--repo", str(repo))
    assert proc.returncode == 2
    assert "guard_error" in proc.stderr or "requires --test and --base" in proc.stderr


def test_guard_raises_on_non_git_repo(tmp_path):
    repo = tmp_path / "notgit"
    repo.mkdir()
    with pytest.raises(GuardError):
        pg.prove_preexisting(repo, "tests/test_thing.py::test_thing", "HEAD" * 1)
