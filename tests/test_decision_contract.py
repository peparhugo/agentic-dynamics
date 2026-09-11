"""Tests for ``core.decision_contract`` — the ONE approval-decision contract (step 2).

The contract exists because three consumers implemented three dialects and none of them read
the COMMITTED bytes. These tests pin the behaviors that close those defects:

* parsing handles the real artifacts, including the d5 shape (an operator line whose value
  embeds the date) and bold/backticked decorations — a real signature is no longer refused
  as unsigned;
* placeholder operators and invalid dates never authorize;
* ``read_committed`` reads a commit's blob, not the working copy (an uncommitted edit is
  invisible; a path deleted after its commit still reads back);
* ``validate_decision`` binds purpose/spec/phase/candidate/tree exactly.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from agentic_dynamics.core import decision_contract as dc


def _git(*args: str, cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "test@example.com", cwd=repo)
    _git("config", "user.name", "test", cwd=repo)
    return repo


def _commit_file(repo: Path, rel: str, text: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _git("add", ".", cwd=repo)
    _git("commit", "-q", "-m", "approval", cwd=repo)
    return _git("rev-parse", "HEAD", cwd=repo).strip()


# --------------------------------------------------------------------------- #
# Parsing — including the artifact shapes that actually refused
# --------------------------------------------------------------------------- #
def test_parses_the_canonical_form():
    text = (
        "---\nstatus: accepted\n---\n# Approval\n\n"
        "- run: run-abc\n- gate: g1\n- candidate: abc123def456\n"
        "- operator: peparhugo\n- date: 2026-09-11\n- spec: my-flow\n- phase: d5\n"
    )
    dec = dc.parse_approval_decision(text)
    assert dec.operator == "peparhugo"
    assert dec.date == "2026-09-11"
    assert dec.candidate_sha == "abc123def456"
    assert dec.run_id == "run-abc"
    assert dec.gate_id == "g1"
    assert dec.spec == "my-flow"
    assert dec.phase == "d5"
    assert dec.purpose == dc.PURPOSE_CHECKPOINT
    assert dc.validate_decision(dec, candidate_sha="abc123def456") == []


def test_parses_the_d5_shape_with_an_inline_date():
    """The d5 incident: a bold inline date + a SIGNED-BY-OPERATOR line whose value carries
    the date. The parser splits operator and date instead of refusing a real signature."""
    text = (
        "# Approval\n\n"
        "**Signed:** **2026-09-11**\n\n"
        "SIGNED-BY-OPERATOR: peparhugo (controller) 2026-09-11\n"
        "Candidate: `abc123def456`\n"
    )
    dec = dc.parse_approval_decision(text)
    assert dec.operator == "peparhugo (controller)"
    assert dec.date == "2026-09-11"
    assert dec.candidate_sha == "abc123def456"
    assert dc.validate_decision(dec, candidate_sha="abc123def456") == []


def test_bold_and_backticked_values_are_cleaned():
    dec = dc.parse_approval_decision("**Operator:** `peparhugo`\n**Date:** **2026-09-11**\n")
    assert dec.operator == "peparhugo"
    assert dec.date == "2026-09-11"


def test_missing_fields_stay_empty_and_fail_validation():
    dec = dc.parse_approval_decision("# Approval\n\ncandidate: abc123def456\n")
    assert set(dc.validate_decision(dec, candidate_sha="abc123def456")) == {"operator", "date"}


def test_placeholder_operators_refuse():
    for who in ("", "operator", "<your signature>", "A", "todo", "aio"):
        assert dc.operator_is_placeholder(who), who
    for who in ("peparhugo", "pepa hugo", "dr-seuss"):
        assert not dc.operator_is_placeholder(who), who


def test_date_validity():
    assert dc.date_is_valid("2026-09-11")
    assert dc.date_is_valid("2026-09-11T10:00:00+00:00")
    assert not dc.date_is_valid("")
    assert not dc.date_is_valid("nonsense")


# --------------------------------------------------------------------------- #
# Validation — the decision binds the exact act
# --------------------------------------------------------------------------- #
def test_validate_decision_binds_every_dimension():
    dec = dc.parse_approval_decision(
        "operator: peparhugo\ndate: 2026-09-11\ncandidate: abc123def456\n"
        "spec: flow\nphase: d5\npurpose: tree_reuse\ntree: deadbeef\nrun: run-1\n"
    )
    assert (
        dc.validate_decision(
            dec,
            purpose=dc.PURPOSE_TREE_REUSE,
            spec="flow",
            phase="d5",
            candidate_sha="abc123def456ffff",
            tree="deadbeef",
        )
        == []
    )
    assert "purpose" in dc.validate_decision(dec, purpose=dc.PURPOSE_CHECKPOINT)
    assert "spec" in dc.validate_decision(dec, spec="other")
    assert "phase" in dc.validate_decision(dec, phase="d4")
    assert "candidate_sha" in dc.validate_decision(dec, candidate_sha="999999")
    assert "tree" in dc.validate_decision(dec, tree="cafebabe")


def test_undeclared_purpose_passes_but_a_declared_mismatch_fails():
    """A legacy artifact (written before the purpose vocabulary) is judged by its path binding;
    a DECLARED purpose must match the act it authorizes."""
    legacy = dc.parse_approval_decision("operator: peparhugo\ndate: 2026-09-11\n")
    assert "purpose" not in dc.validate_decision(legacy, purpose=dc.PURPOSE_TREE_REUSE)
    declared = dc.parse_approval_decision(
        "operator: peparhugo\ndate: 2026-09-11\npurpose: checkpoint\n"
    )
    assert "purpose" in dc.validate_decision(declared, purpose=dc.PURPOSE_TREE_REUSE)


def test_candidate_sha_accepts_either_abbreviation():
    dec = dc.parse_approval_decision(
        "operator: peparhugo\ndate: 2026-09-11\ncandidate: abc123de\n"
    )
    assert dc.validate_decision(dec, candidate_sha="abc123de1234567890") == []


# --------------------------------------------------------------------------- #
# read_committed — the immutable bytes, never the checkout
# --------------------------------------------------------------------------- #
def test_read_committed_sees_the_commit_not_the_working_copy(tmp_path):
    repo = _repo(tmp_path)
    rel = "approvals/flow/d5_approval.md"
    commit = _commit_file(repo, rel, "operator: committed\n")

    # the uncommitted-edit defect: the working copy now says something else
    (repo / rel).write_text("operator: edited-in-working-copy\n", encoding="utf-8")

    assert dc.read_committed(repo, commit, rel) == "operator: committed\n"
    assert dc.read_committed(repo, commit, "approvals/flow/absent.md") is None


def test_read_committed_still_reads_a_path_deleted_after_commit(tmp_path):
    repo = _repo(tmp_path)
    rel = "approvals/flow/d5_approval.md"
    commit = _commit_file(repo, rel, "operator: committed\n")
    _git("rm", "-q", rel, cwd=repo)
    _git("commit", "-q", "-m", "remove", cwd=repo)

    assert dc.read_committed(repo, commit, rel) == "operator: committed\n"
    assert dc.read_committed(repo, "deadbeef", rel) is None
