"""Pre-existing-drift guard (``control_db_evidence`` e5) — "pre-existing" must be PROVEN.

The mislabeling pattern this guard kills: an author whose branch breaks a harness test
calls the failure "pre-existing drift" to wave it away. On 2026-09-02 that exact claim was
made twice — the ``control_db_followups`` f4/f5 commits called the f7 harness failure
(``tests/test_doc_lifecycle.py::test_readme_spec_counts_match_index``) "the known
pre-existing f0 drift"; the adversarial review then disproved it at the merge base
``ec3eb1c13`` (README 178 / index 178 in sync → the test PASSED at base, so the failure was
branch-introduced). The claim was false, and nothing mechanical refused it.

This module closes that gap. A review doc may call a failing test "pre-existing" ONLY when
this guard passes for that test at that merge-base. The guard is deterministic, fast and
model-free: resolve the base sha, check it out into a temporary git worktree, run the SAME
pytest node there, and compare the base outcome against the head outcome. No LLM call, no
heuristic — a pytest exit classification on both trees.

Verdicts (the claim is allowed iff ``verdict == pre-existing``):

* ``pre-existing`` — the test FAILS at the merge-base AND FAILS at the head. The failure
  genuinely exists at the base, so the author may call it pre-existing (guard PASSES).
* ``branch-introduced`` — the test PASSES at the merge-base (or is absent there — a failing
  test that did not exist at the base is new to the branch) but FAILS at the head. The
  mislabel is caught mechanically (guard FAILS).
* ``not-failing`` — the test does not fail at the head; there is no failure to explain.
* ``unverifiable`` — the base tree could not run the node (collection/import error, missing
  base sha, non-git repo). A claim that cannot be reproduced is NOT accepted; this is a
  fail-closed refusal, never a pass.

The guard emits a one-line machine citation that a review doc must embed when it calls a
failure pre-existing::

    preexisting-guard-evidence: verdict=pre-existing base=<sha> head=<sha>
        test=<node id> before=FAIL after=FAIL

``flag_uncited_preexisting_claims`` is the doc-side of the same rule: it reads a review
doc's text and flags every line that makes a pre-existing claim about a failure unless the
doc carries a valid ``pre-existing`` evidence citation. A review phase or operator runs it on
a review doc before accepting the "pre-existing" label; one that cites the guard is accepted,
one that claims without it is flagged.

CLI: ``scripts/check_preexisting.py`` (``agentic-dynamics validate preexisting``).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass
from pathlib import Path

#: Schema tag on the machine evidence record, so a consumer knows what document it received.
GUARD_SCHEMA = "preexisting-guard/v1"

#: Outcome vocabulary for a single pytest run on one node.
OUTCOME_PASS = "pass"
OUTCOME_FAIL = "fail"
OUTCOME_ABSENT = "absent"
OUTCOME_ERROR = "error"

#: Verdict vocabulary. ``pre-existing`` is the ONLY verdict that lets an author call a
#: failure pre-existing; every other verdict is a mechanical refusal.
VERDICT_PRE_EXISTING = "pre-existing"
VERDICT_BRANCH_INTRODUCED = "branch-introduced"
VERDICT_NOT_FAILING = "not-failing"
VERDICT_UNVERIFIABLE = "unverifiable"

#: The one-line citation marker review docs must carry when they call a failure pre-existing.
#: Format: ``preexisting-guard-evidence: verdict=pre-existing base=<sha> head=<sha>
#: test=<node id> before=FAIL after=FAIL`` (test is the last field; it may contain ``::``).
EVIDENCE_MARKER = "preexisting-guard-evidence:"

_PRE_TOKEN = r"(?:pre-?\s*existing|preexisting|pre existing)"
#: A pre-existing CLAIM = a line asserting a failure/test/gate/harness is pre-existing
#: (the mislabel shape). Requires BOTH a pre-existing token AND a failure-context token on
#: the same line, so "the pre-existing codebase" alone is not a claim.
_CLAIM_RE = re.compile(
    rf"\b{_PRE_TOKEN}\b.{{0,80}}\b(fail(?:ed|ing|ure)?s?|red|drift|regression|broken|break|"
    rf"gate|harness|test|pytest)\b|\b(fail(?:ed|ing|ure)?s?|red|drift|regression|broken|"
    rf"break|gate|harness|test|pytest)\b.{{0,80}}\b{_PRE_TOKEN}\b",
    re.IGNORECASE,
)
#: A negated mention ("NOT pre-existing", "never pre-existing") is a denial, not a claim —
#: it must never be flagged (the f6 adversarial's "not pre-existing" corrections say exactly
#: the opposite of the mislabel and need no citation).
_NEGATED_RE = re.compile(
    rf"\b(not|never|no|isn.t|wasn.t|aren.t|weren.t|no longer)\s+(?:a\s+)?{_PRE_TOKEN}\b|"
    rf"\b{_PRE_TOKEN}\b[^\n]{{0,40}}\b(not|false|incorrect|disproven|debunked)\b",
    re.IGNORECASE,
)

#: One evidence citation line, parsed back into :class:`PreexistingEvidence`.
_EVIDENCE_RE = re.compile(
    rf"{EVIDENCE_MARKER}\s+verdict=(\S+)\s+base=(\S+)\s+head=(\S+)\s+test=(\S+)\s+"
    rf"before=(\S+)\s+after=(\S+)"
)


class GuardError(RuntimeError):
    """A guard could not run (non-git repo, unresolvable sha, unreadable worktree)."""


@dataclass(frozen=True)
class PreexistingEvidence:
    """The guard's record: base/head shas, the node id, and before/after outcomes.

    ``verdict == VERDICT_PRE_EXISTING`` is the ONLY state in which the author may call the
    failure pre-existing. ``citation()`` renders the one-line marker a review doc must embed.
    """

    base_sha: str
    head_sha: str
    test: str
    base_outcome: str
    head_outcome: str
    verdict: str
    note: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"schema": GUARD_SCHEMA, **asdict(self)}

    def citation(self) -> str:
        """The one-line evidence a review doc embeds when it calls this failure pre-existing."""
        return (
            f"{EVIDENCE_MARKER} verdict={self.verdict} base={self.base_sha} "
            f"head={self.head_sha} test={self.test} before={self.base_outcome} "
            f"after={self.head_outcome}"
        )

    @classmethod
    def from_citation(cls, line: str) -> PreexistingEvidence | None:
        """Parse one evidence citation line back into an evidence record, or ``None``."""
        m = _EVIDENCE_RE.search(line)
        if not m:
            return None
        verdict, base, head, test, before, after = m.groups()
        return cls(
            base_sha=base,
            head_sha=head,
            test=test,
            base_outcome=before,
            head_outcome=after,
            verdict=verdict,
        )


def _git(repo: Path, *args: str) -> str:
    """Run a read-only git command against ``repo``; raise :class:`GuardError` on failure."""
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise GuardError(f"git {' '.join(args)} failed in {repo}: {(proc.stderr or '').strip()}")
    return proc.stdout.strip()


def _resolve_sha(repo: Path, rev: str) -> str:
    """Resolve ``rev`` (a full sha, short sha, or ref) to a commit sha in ``repo``."""
    return _git(repo, "rev-parse", "--verify", f"{rev}^{{commit}}")


@contextmanager
def _worktree_at(repo: Path, sha: str, *, worktrees_root: Path | None = None) -> Iterator[Path]:
    """Check out ``sha`` into a temporary detached worktree; yield its root; always clean up."""
    parent = Path(
        tempfile.mkdtemp(prefix="preexisting_", dir=str(worktrees_root) if worktrees_root else None)
    )
    tree = parent / "tree"
    try:
        _git(repo, "worktree", "add", "--detach", str(tree), sha)
        yield tree
    finally:
        with suppress(GuardError):
            _git(repo, "worktree", "remove", "--force", str(tree))
        shutil.rmtree(parent, ignore_errors=True)


def _classify(result: dict) -> str:
    """Map a ``run_suite`` result to a single-node outcome for the guard.

    Ordering is deliberate: a failed assertion is a FAIL; a collection/import error is an
    ERROR (the node could not be run at that tree); nothing collected (missing file, or a
    node id that matches nothing) is ABSENT — a test that does not exist at a tree cannot be
    pre-existing there; everything else is PASS.
    """
    if result.get("failed", 0) > 0:
        return OUTCOME_FAIL
    if result.get("errors", 0) > 0:
        return OUTCOME_ERROR
    if result.get("total", 0) == 0:
        return OUTCOME_ABSENT
    return OUTCOME_PASS


def prove_preexisting(
    repo: Path | str,
    test: str,
    base: str,
    *,
    head: str = "HEAD",
    timeout: int = 120,
    worktrees_root: Path | str | None = None,
    run_node=None,
) -> PreexistingEvidence:
    """Prove whether ``test`` fails at ``base`` (before) and at ``head`` (after).

    ``repo`` is the git checkout under review (typically the branch worktree). ``base`` is
    the merge-base sha the author claims the failure predates; ``head`` defaults to the
    checkout's HEAD. Both are resolved, each is checked out into a temporary worktree, and
    the SAME pytest node is run on each tree. No model call, no heuristic — the verdict is a
    pure function of the two pytest outcomes.

    ``run_node(worktree, node_id) -> outcome`` is injectable for tests that must control the
    pytest boundary; it defaults to :func:`runtime.test_runner.run_suite`'s python runner.
    """
    repo = Path(repo).resolve()
    if run_node is None:
        from agentic_dynamics.runtime.test_runner import run_suite  # local import: optional dep

        def run_node(worktree: Path, node: str) -> str:  # noqa: ANN001
            return _classify(run_suite(worktree, "python", target=node, timeout=timeout))

    root = Path(worktrees_root).resolve() if worktrees_root is not None else None
    head_sha = _resolve_sha(repo, head)
    base_sha = _resolve_sha(repo, base)

    try:
        with _worktree_at(repo, head_sha, worktrees_root=root) as head_tree:
            head_outcome = run_node(head_tree, test)
        with _worktree_at(repo, base_sha, worktrees_root=root) as base_tree:
            base_outcome = run_node(base_tree, test)
    except GuardError:
        raise

    if head_outcome != OUTCOME_FAIL:
        return PreexistingEvidence(
            base_sha=base_sha,
            head_sha=head_sha,
            test=test,
            base_outcome=base_outcome,
            head_outcome=head_outcome,
            verdict=VERDICT_NOT_FAILING,
            note="the test does not fail at the head; there is no failure to explain",
        )
    if base_outcome == OUTCOME_FAIL:
        return PreexistingEvidence(
            base_sha=base_sha,
            head_sha=head_sha,
            test=test,
            base_outcome=base_outcome,
            head_outcome=head_outcome,
            verdict=VERDICT_PRE_EXISTING,
            note="the failure exists at the merge-base — the author may call it pre-existing",
        )
    if base_outcome in (OUTCOME_PASS, OUTCOME_ABSENT):
        reason = (
            "the test PASSES at the merge-base"
            if base_outcome == OUTCOME_PASS
            else "the test is ABSENT at the merge-base (a failing test that did not exist "
            "at the base is new to the branch)"
        )
        return PreexistingEvidence(
            base_sha=base_sha,
            head_sha=head_sha,
            test=test,
            base_outcome=base_outcome,
            head_outcome=head_outcome,
            verdict=VERDICT_BRANCH_INTRODUCED,
            note=f"{reason}; the failure is branch-introduced, not pre-existing",
        )
    return PreexistingEvidence(
        base_sha=base_sha,
        head_sha=head_sha,
        test=test,
        base_outcome=base_outcome,
        head_outcome=head_outcome,
        verdict=VERDICT_UNVERIFIABLE,
        note="the base tree could not run the node — an unverifiable claim is never accepted",
    )


def flag_uncited_preexisting_claims(text: str) -> list[str]:
    """Flag pre-existing CLAIMS in a review doc that carry no guard evidence citation.

    A claim is a line that asserts a failure/test/gate/harness is pre-existing (token + a
    failure-context token on the same line, negation-aware: "NOT pre-existing" is a denial,
    never flagged). A review doc that makes such a claim is accepted ONLY if it embeds a
    ``preexisting-guard-evidence: ... verdict=pre-existing`` citation (a valid ``pre-existing``
    verdict means the guard proved the failure at the base). Lines that ARE the citation are
    never flagged.

    Returns a list of ``"<line>: <text>"`` flagged claims; empty means the doc is accepted.
    """
    flagged: list[str] = []
    has_pre_existing_evidence = False
    for line in text.splitlines():
        parsed = PreexistingEvidence.from_citation(line)
        if parsed is not None and parsed.verdict == VERDICT_PRE_EXISTING:
            has_pre_existing_evidence = True
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _EVIDENCE_RE.search(line):
            continue
        if _NEGATED_RE.search(line):
            continue
        if _CLAIM_RE.search(line) and not has_pre_existing_evidence:
            flagged.append(f"{lineno}: {line.strip()}")
    return flagged
