"""Relabel tree-identity gate tests (cap_runner_hardening2 §Gap 2).

The gate closes the revamp2 relabel: attempt A's tree was reset away (discarded), attempt B
(the "resume") re-committed a byte-IDENTICAL copy under compliant ``[workflow]`` messages —
``git diff f6fc35edf 20eeb801b`` is empty, both trees are
``f22dbe994439074b47586b0846c033becbf53400``. The merged commit-prefix enforcement checks the
MESSAGE, and the relabel's messages matched — so the relabel passed. This gate records every
discarded tree on a durable ledger (``discarded_trees.jsonl``, keyed
``(spec, branch, tree_hash, discarded_at)``) and fails any phase whose committed tree is
EXACTLY a recorded discarded tree with the identical-tree proof — unless an operator-signed
approval artifact (``approvals/<spec>/<phase>_tree_reuse.md``, committed before the phase,
present at the phase's pre-head) names the tree + phase + a real operator signature + a date.

The revamp2 RELABEL SCENARIO is REPLAYED on the REAL hashes: the test materializes the actual
attempt-A commit's tree hermetically (``git archive f6fc35edf`` → fresh commit reproduces the
exact tree — git trees are content-addressed, so the copy is byte-identical), records it as
discarded, then re-presents it as a phase's fresh work under a compliant ``[workflow]`` message
(``--allow-empty`` keeps the tree byte-identical). The gate fires RELABEL; with the approval
committed first it passes.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agentic_dynamics.experiment.experiment_spec import load_spec
from agentic_dynamics.runtime.workflow_runner import (
    _git_tree_hash,
    _operator_is_placeholder,
    approval_authorizes_tree,
    load_discarded_trees,
    record_discarded_tree,
    run_workflow,
)

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "workflows" / "repository" / "control_room_portal.yaml"

#: The revamp2 measured relabel (design §Gap 2): attempt A's commit (discarded) and attempt
#: B's resume commit share ONE byte-identical tree.
REVAMP2_ATTEMPT_A = "f6fc35edf"  # "docs: record deployed DOM gate runs"
REVAMP2_ATTEMPT_B = "20eeb801b"  # "[workflow] p3_dom_verification — Deliver the site's IMPLEMENTED visual system:"
REVAMP2_TREE = "f22dbe994439074b47586b0846c033becbf53400"
REVAMP2_GOAL = "Deliver the site's IMPLEMENTED visual system"

MINIMAL_SPEC_YAML = """\
name: relabel_gate_test
question: relabel gate fixture
version: "0.1"
artifact_kind: workflow
intent: mutate
side_effects:
  repository: true
  external_services: false
workflow:
  kind: agent_task
  params:
    language: python
    phases:
      - name: scope
        kind: agent
        timeout: 120
        prompt: |
          {goal}
factors:
  - {name: model, levels: [deepseek/deepseek-v4-flash]}
design: factorial
rules: []
metrics: []
comparison: null
"""


def _minimal_spec(tmp_path: Path):
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(MINIMAL_SPEC_YAML)
    return load_spec(spec_path)


def _fake_agent(**overrides):
    from types import SimpleNamespace

    base = dict(
        prompt_tokens=10, completion_tokens=20, reasoning_tokens=5, total_tokens=35,
        estimated_cost_usd=0.001, files_created=[], files_modified=[], final_response="done",
        ok=True, exit_code=0, error="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def _git_init(workdir: Path) -> None:
    _git("init", "-q", cwd=workdir)
    _git("config", "user.email", "t@t", cwd=workdir)
    _git("config", "user.name", "t", cwd=workdir)
    # Auto-gc OFF in every test repo this module builds. The materialized attempt-A tree is
    # 27,504 files (~30k loose objects — far above gc.auto=6700), so the fixture's `git
    # commit` detaches a background `git gc` that repacks and DELETES the loose objects
    # WHILE the replay tests hardlink-copy them: `os.link` → ENOENT → `shutil.Error`
    # (the 2026-09-12 CI flake, confirmed from the raw CI log — thousands of
    # `[Errno 2] ... .git/objects/74/...` entries). The hardlink-copy contract holds only
    # if nothing mutates the object store; the copies inherit this config (.git/ is copied)
    # so their own commits stay stable too.
    _git("config", "gc.auto", "0", cwd=workdir)
    _git("config", "gc.autoDetach", "false", cwd=workdir)
    _git("config", "maintenance.auto", "false", cwd=workdir)


def _materialize_commit_tree(commit: str, target: Path) -> str:
    """Materialize ``commit``'s full tree into ``target`` (a standalone git repo).

    Git-native by construction (2026-09-13 CI fix): a shared clone + detached checkout
    materializes the tree from the commit OBJECTS — no ``git archive | tar`` + ``git add``
    round-trip through the filesystem. That round-trip proved environment-sensitive: newer
    CI runner images (tar/mode/eol drift) reproduced a DIFFERENT tree hash for the same
    commit while every local run stayed byte-identical. Git trees are content-addressed, so
    checking the commit out reproduces the EXACT tree hash by construction — the
    byte-identity the replay tests depend on. Returns the hash.
    """
    subprocess.run(
        ["git", "clone", "-q", "--shared", "--no-checkout", str(REPO), str(target)],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "-q", "--detach", commit],
        cwd=target, check=True, capture_output=True,
    )
    _git_init(target)
    return _git("rev-parse", "HEAD^{tree}", cwd=target).stdout.strip()


#: The real-tree materialization runs ONCE per module run (a shared clone + detached
#: checkout — git-native, no tar round-trip), then each replay test copies it via hardlinks
#: (``os.link`` — git never mutates objects/index in place, and the repo carries ``gc.auto=0``
#: so nothing DELETES them either; a fresh commit in one copy never leaks into another). This
#: keeps the revamp2 REPLAY on the REAL byte-identical tree while cutting the repeated
#: materializations to one (test_suite_speed p2).
@pytest.fixture(scope="module")
def attempt_a_template(tmp_path_factory):
    """The hermetic attempt-A tree materialized once; the replay tests copy it in ~1s."""
    wd = tmp_path_factory.mktemp("attempt_a_template") / "wd"
    wd.mkdir()
    tree = _materialize_commit_tree(REVAMP2_ATTEMPT_A, wd)
    assert tree == REVAMP2_TREE  # the materialization proof, validated once per module run
    # The hardlink-copy contract: a background gc must not race the copies (2026-09-12 flake).
    assert _git("config", "gc.auto", cwd=wd).stdout.strip() == "0"
    return wd


def _copy_attempt_a(template: Path, target: Path) -> str:
    """Hardlink-copy the shared attempt-A tree into ``target``; return its tree hash.

    ``target`` must not already exist (``shutil.copytree`` creates it). The copy is then
    reset to a pristine HEAD (``reset --hard`` + ``clean -fdx``): the shared module fixture
    can accumulate runtime junk (pytest bytecode, SQLite WAL sidecars under the corpus
    artifacts) from concurrent suite activity, and a phase commit sweeps whatever sits in
    the worktree — the CI-only tree drift (2026-09-13). A pristine copy keeps every replay
    phase's tree exactly ``base + what the test writes``.
    """
    shutil.copytree(template, target, copy_function=os.link)
    subprocess.run(["git", "reset", "--hard", "-q", "HEAD"], cwd=target, check=True)
    subprocess.run(["git", "clean", "-fdxq"], cwd=target, check=True)
    # Runtime junk the wider suite can drop into shared corpus paths (SQLite WAL sidecars,
    # bytecode) must never enter a replay phase's commit: exclude it in THIS copy's
    # info/exclude (worktree-local; no effect on the tree hash).
    exclude = target / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text(
        (exclude.read_text() if exclude.exists() else "")
        + "\n__pycache__/\n*.pyc\n*.pyo\n*.db-shm\n*.db-wal\n"
    )
    return _git("rev-parse", "HEAD^{tree}", cwd=target).stdout.strip()


def _approval_text(tree_hash: str, *, phase: str = "scope", operator: str = "jane@example.com",
                   date: str = "2026-08-27") -> str:
    return (
        f"# Tree-reuse approval\n\n"
        f"The operator authorizes reusing the discarded tree below.\n\n"
        f"- tree: {tree_hash}\n"
        f"- phase: {phase}\n"
        f"- operator: {operator}\n"
        f"- date: {date}\n"
    )


# ── the revamp2 replay anchors ───────────────────────────────────────────────


def test_real_revamp2_trees_are_byte_identical():
    """The design's measured claim, anchored on the REAL repo objects: attempt A and attempt B
    share one tree and ``git diff`` between them is empty — the relabel the message gate cannot
    see. This is the regression the tree gate exists to catch."""
    a = _git("rev-parse", f"{REVAMP2_ATTEMPT_A}^{{tree}}", cwd=REPO).stdout.strip()
    b = _git("rev-parse", f"{REVAMP2_ATTEMPT_B}^{{tree}}", cwd=REPO).stdout.strip()
    assert a == b == REVAMP2_TREE
    diff = subprocess.run(["git", "diff", "--quiet", REVAMP2_ATTEMPT_A, REVAMP2_ATTEMPT_B],
                          cwd=REPO, capture_output=True)
    assert diff.returncode == 0  # empty diff


def test_materialized_attempt_a_reproduces_the_exact_tree(attempt_a_template):
    """The hermetic replay copy is byte-identical to the real commit's tree.

    The materialization proof now runs once per module (in the ``attempt_a_template``
    fixture — the real ``_materialize_commit_tree`` against the real 298MB tree); a hardlink
    copy of that shared tree is byte-identical by construction (git trees are content-
    addressed). The assertion is unchanged: the replay tree IS ``REVAMP2_TREE``.
    """
    import tempfile

    wd = Path(tempfile.mkdtemp(prefix="relabel_copy_", dir="/tmp")) / "wd"
    try:
        assert _copy_attempt_a(attempt_a_template, wd) == REVAMP2_TREE
    finally:
        shutil.rmtree(wd.parent, ignore_errors=True)


def test_git_tree_hash_excludes_approvals_and_matches_plain_when_absent(tmp_path):
    """The compared tree EXCLUDES the ``approvals/`` subtree (scaffolding is not work product),
    and equals the plain tree hash whenever the tree has no approvals/ (the common case)."""
    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / "work.txt").write_text("fresh work")
    _git_init(wd)
    _git("add", "-A", cwd=wd)
    _git("commit", "-qm", "seed", cwd=wd)
    plain = _git("rev-parse", "HEAD^{tree}", cwd=wd).stdout.strip()
    assert _git_tree_hash(wd) == plain
    # add an approval artifact → the excluded tree is UNCHANGED
    ap = wd / "approvals" / "relabel_gate_test"
    ap.mkdir(parents=True)
    (ap / "scope_tree_reuse.md").write_text(_approval_text(plain))
    _git("add", "-A", cwd=wd)
    _git("commit", "-qm", "approval", cwd=wd)
    assert _git("rev-parse", "HEAD^{tree}", cwd=wd).stdout.strip() != plain
    assert _git_tree_hash(wd) == plain


# ── the discarded-trees ledger ───────────────────────────────────────────────


def test_record_and_load_discarded_tree_round_trip_and_dedup(tmp_path):
    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / "work.txt").write_text("attempt A work")
    _git_init(wd)
    _git("add", "-A", cwd=wd)
    _git("commit", "-qm", "attempt A", cwd=wd)
    ledger = tmp_path / "discarded_trees.jsonl"

    tree = record_discarded_tree("relabel_gate_test", wd, ledger_path=ledger)
    assert tree == _git("rev-parse", "HEAD^{tree}", cwd=wd).stdout.strip()
    entries = load_discarded_trees("relabel_gate_test", ledger_path=ledger)
    assert len(entries) == 1
    assert entries[0]["spec"] == "relabel_gate_test"
    assert entries[0]["tree_hash"] == tree
    assert entries[0]["branch"] == _git("rev-parse", "--abbrev-ref", "HEAD", cwd=wd).stdout.strip()
    assert entries[0]["discarded_at"]
    assert entries[0]["reason"] == "reset"

    # idempotent: re-recording the same (spec, branch, tree) is a no-op
    record_discarded_tree("relabel_gate_test", wd, ledger_path=ledger)
    assert len(load_discarded_trees("relabel_gate_test", ledger_path=ledger)) == 1


def test_record_discarded_tree_skips_a_non_git_workdir(tmp_path):
    assert record_discarded_tree("s", tmp_path / "missing", ledger_path=tmp_path / "l.jsonl") == ""
    assert load_discarded_trees("s", ledger_path=tmp_path / "l.jsonl") == []


# ── the relabel REPLAY (both directions) ─────────────────────────────────────


def test_relabel_without_approval_fails_with_identical_tree_proof(tmp_path, attempt_a_template):
    """The revamp2 replay, FAIL direction: the discarded attempt-A tree re-committed under a
    compliant ``[workflow]`` message (byte-identical tree) fails the phase RELABEL with the
    identical-tree proof — the identical tree IS the proof (git diff is empty)."""
    spec = _minimal_spec(tmp_path)
    wd = tmp_path / "wd"
    assert _copy_attempt_a(attempt_a_template, wd) == REVAMP2_TREE
    attempt_a_head = _git("rev-parse", "HEAD", cwd=wd).stdout.strip()
    ledger = tmp_path / "discarded_trees.jsonl"
    assert record_discarded_tree(spec.name, wd, ledger_path=ledger) == REVAMP2_TREE

    def agent(prompt, *, model, backend, workdir, **kwargs):
        subprocess.run(
            ["git", "commit", "-q", "--allow-empty", "-m", "[workflow] scope — g"],
            cwd=workdir, check=True,
        )
        return _fake_agent()

    result = run_workflow(
        spec, goal="g", model="m", workdir=wd, run_agentic_fn=agent,
        discarded_trees_ledger=ledger,
    )
    p = result.phases[0]
    assert p.status == "failed"
    assert "RELABEL" in p.error
    assert REVAMP2_TREE in p.error
    gate = p.relabel_gate
    assert gate is not None
    assert gate["reason"] == "RELABEL"
    assert gate["phase_tree"] == REVAMP2_TREE
    assert gate["identical_tree_proof"]["discarded_tree_hash"] == REVAMP2_TREE
    assert gate["identical_tree_proof"]["phase_tree_hash"] == REVAMP2_TREE
    assert gate["identical_tree_proof"]["empty_diff"] is True
    assert gate["matching_discarded_tree"]["tree_hash"] == REVAMP2_TREE
    # the discarded record's commit is the worktree commit whose tree was discarded (the
    # materialized attempt A — a different object id than the upstream f6fc35edf, same tree)
    assert gate["matching_discarded_tree"]["commit"] == attempt_a_head
    assert gate["approval"]["authorized"] is False
    assert result.ok is False


def _gate_diag(wd: Path, spec_name: str, ledger: Path) -> str:
    """Diagnose why the relabel gate did not fire (used only in assertion messages).

    The gate is silent by design when its (tree, branch) match finds nothing, so a CI-only
    miss needs the raw comparison values in the failure output (2026-09-13). When the
    approvals-excluded phase tree still differs from the base commit, the diff names the
    offending paths outright — the phase tree is compared against ``REVAMP2_ATTEMPT_A``
    (available in the copy via the shared object store).
    """
    import subprocess

    from agentic_dynamics.runtime.workflow_runner import (
        _git_tree_hash,
        _worktree_branch,
        load_discarded_trees,
    )

    def _ls(rev: str) -> dict[str, tuple[str, str]]:
        out = subprocess.run(
            ["git", "ls-tree", "-r", rev], cwd=wd, capture_output=True, text=True,
        ).stdout
        entries: dict[str, tuple[str, str]] = {}
        for line in out.splitlines():
            if not line:
                continue
            meta, path = line.split("\t", 1)
            mode, _otype, sha = meta.split()
            entries[path] = (mode, sha)
        return entries

    try:
        head, base = _ls("HEAD"), _ls(REVAMP2_ATTEMPT_A)
        extra = sorted(set(head) - set(base) - {"approvals"})
        extra = [p for p in extra if not p.startswith("approvals/")][:12]
        missing = sorted(set(base) - set(head))[:12]
        changed = sorted(
            p for p in (set(head) & set(base)) if head[p] != base[p]
        )[:12]
        diff = f" extra_paths={extra!r} missing_paths={missing!r} changed_paths={changed!r}"
    except Exception as exc:  # noqa: BLE001 — diagnosis only
        diff = f" (path diff unavailable: {exc})"

    return (
        f"phase_tree={_git_tree_hash(wd)!r} branch={_worktree_branch(wd)!r} "
        f"ledger={load_discarded_trees(spec_name, ledger_path=ledger)!r}{diff}"
    )


def test_relabel_with_operator_approval_passes(tmp_path, attempt_a_template):
    """The revamp2 replay, PASS direction: the same discarded tree re-presented, but the
    operator approved the reuse FIRST (an approval artifact committed before the phase, present
    at the pre-head, naming the tree + phase + a real signature + a date) — the reuse passes."""
    spec = _minimal_spec(tmp_path)
    wd = tmp_path / "wd"
    assert _copy_attempt_a(attempt_a_template, wd) == REVAMP2_TREE
    ledger = tmp_path / "discarded_trees.jsonl"
    assert record_discarded_tree(spec.name, wd, ledger_path=ledger) == REVAMP2_TREE

    # the operator signs + commits the approval BEFORE the phase runs
    ap = wd / "approvals" / spec.name
    ap.mkdir(parents=True)
    (ap / "scope_tree_reuse.md").write_text(_approval_text(REVAMP2_TREE))
    _git("add", "-A", "--", "approvals", cwd=wd)
    _git("commit", "-qm", "operator approval", cwd=wd)

    def agent(prompt, *, model, backend, workdir, **kwargs):
        subprocess.run(
            ["git", "commit", "-q", "--allow-empty", "-m", "[workflow] scope — g"],
            cwd=workdir, check=True,
        )
        return _fake_agent()

    result = run_workflow(
        spec, goal="g", model="m", workdir=wd, run_agentic_fn=agent,
        discarded_trees_ledger=ledger,
    )
    p = result.phases[0]
    assert p.status == "ok"  # the approved reuse keeps the phase ok
    gate = p.relabel_gate
    assert gate is not None, _gate_diag(wd, spec.name, ledger)
    assert gate["reason"] == "APPROVED"
    assert gate["phase_tree"] == REVAMP2_TREE
    assert gate["approval"]["authorized"] is True
    assert gate["approval"]["operator"] == "jane@example.com"
    assert result.ok is True


def test_approval_committed_during_the_phase_is_not_an_approval(tmp_path, attempt_a_template):
    """The gaming move: the phase itself commits the approval artifact to cover its own relabel
    — an approval present only at the post-phase HEAD, not at the pre-head, is refused."""
    spec = _minimal_spec(tmp_path)
    wd = tmp_path / "wd"
    assert _copy_attempt_a(attempt_a_template, wd) == REVAMP2_TREE
    ledger = tmp_path / "discarded_trees.jsonl"
    assert record_discarded_tree(spec.name, wd, ledger_path=ledger) == REVAMP2_TREE

    def agent(prompt, *, model, backend, workdir, **kwargs):
        # the relabel + its own "approval", committed DURING the phase
        ap = Path(workdir) / "approvals" / spec.name
        ap.mkdir(parents=True)
        (ap / "scope_tree_reuse.md").write_text(_approval_text(REVAMP2_TREE))
        subprocess.run(["git", "add", "-A", "--", "approvals"], cwd=workdir, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "[workflow] scope — g"],
            cwd=workdir, check=True,
        )
        return _fake_agent()

    result = run_workflow(
        spec, goal="g", model="m", workdir=wd, run_agentic_fn=agent,
        discarded_trees_ledger=ledger,
    )
    p = result.phases[0]
    assert p.status == "failed", f"status={p.status!r} error={p.error!r} {_gate_diag(wd, spec.name, ledger)}"
    assert "RELABEL" in p.error
    assert p.relabel_gate["approval"]["authorized"] is False
    assert p.relabel_gate["approval"]["present_at_pre_head"] is False
    assert p.relabel_gate["approval"]["failed_checks"] == ["committed_before_phase"]


def test_genuine_resume_of_never_discarded_work_never_fires(tmp_path):
    """A phase committing genuinely NEW work (a tree never recorded as discarded) never fires
    the gate — the legit resume path (matching hashes + commits) is untouched."""
    spec = _minimal_spec(tmp_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    _git("commit", "-q", "--allow-empty", "-m", "seed", cwd=wd)
    ledger = tmp_path / "discarded_trees.jsonl"

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "scope.md").write_text("---\nstatus: accepted\n---\n\ngenuine fresh work")
        subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "[workflow] scope — g"], cwd=workdir, check=True,
        )
        return _fake_agent()

    result = run_workflow(
        spec, goal="g", model="m", workdir=wd, run_agentic_fn=agent,
        discarded_trees_ledger=ledger,
    )
    p = result.phases[0]
    assert p.status == "ok"
    assert p.relabel_gate is None
    assert result.ok is True


# ── approval-contract validation (unit) ─────────────────────────────────────


def _approved_unit(tmp_path, **approval_overrides) -> tuple[Path, str, str]:
    """A worktree whose HEAD tree is recorded discarded, with the approval in place at pre-head.
    Returns (workdir, tree_hash, ledger_path)."""
    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / "work.txt").write_text("x")
    _git_init(wd)
    _git("add", "-A", cwd=wd)
    _git("commit", "-qm", "seed", cwd=wd)
    tree = _git("rev-parse", "HEAD^{tree}", cwd=wd).stdout.strip()
    ledger = tmp_path / "discarded_trees.jsonl"
    record_discarded_tree("relabel_gate_test", wd, ledger_path=ledger)
    return wd, tree, str(ledger)


def test_approval_contract_validates_signature_identity_and_dates():
    # A non-placeholder operator + a real date is what makes the artifact an approval.
    assert _operator_is_placeholder("") is True
    assert _operator_is_placeholder("operator") is True
    assert _operator_is_placeholder("Your Name") is True
    assert _operator_is_placeholder("sign here") is True
    assert _operator_is_placeholder("TODO") is True
    assert _operator_is_placeholder("x") is True            # a single initial is not a signature
    assert _operator_is_placeholder("jane.doe@example.com") is False
    assert _operator_is_placeholder("Jane Doe") is False


def test_approval_authorizes_only_when_all_contract_fields_hold(tmp_path):
    wd, tree, ledger = _approved_unit(tmp_path)

    # (1) no artifact → refused
    authorized, evidence = approval_authorizes_tree(wd, "relabel_gate_test", "scope", tree, pre_head="HEAD")
    assert authorized is False
    assert evidence["present_at_pre_head"] is False

    # (2) a full valid approval → authorized
    ap = wd / "approvals" / "relabel_gate_test"
    ap.mkdir(parents=True)
    (ap / "scope_tree_reuse.md").write_text(_approval_text(tree))
    _git("add", "-A", cwd=wd)
    _git("commit", "-qm", "approval", cwd=wd)
    pre_head = _git("rev-parse", "HEAD", cwd=wd).stdout.strip()
    authorized, evidence = approval_authorizes_tree(
        wd, "relabel_gate_test", "scope", tree, pre_head=pre_head
    )
    assert authorized is True
    assert evidence["present_at_pre_head"] is True

    # (3) placeholder signature → refused
    (ap / "scope_tree_reuse.md").write_text(_approval_text(tree, operator="your name"))
    _git("add", "-A", cwd=wd)
    _git("commit", "-qm", "placeholder", cwd=wd)
    pre_head = _git("rev-parse", "HEAD", cwd=wd).stdout.strip()
    authorized, evidence = approval_authorizes_tree(
        wd, "relabel_gate_test", "scope", tree, pre_head=pre_head
    )
    assert authorized is False
    assert evidence["failed_checks"] == ["operator"]

    # (4) wrong tree → refused
    (ap / "scope_tree_reuse.md").write_text(_approval_text("0" * 40))
    _git("add", "-A", cwd=wd)
    _git("commit", "-qm", "wrong tree", cwd=wd)
    pre_head = _git("rev-parse", "HEAD", cwd=wd).stdout.strip()
    authorized, evidence = approval_authorizes_tree(
        wd, "relabel_gate_test", "scope", tree, pre_head=pre_head
    )
    assert authorized is False
    assert evidence["failed_checks"] == ["tree"]

    # (5) wrong phase → refused
    (ap / "scope_tree_reuse.md").write_text(_approval_text(tree, phase="other_phase"))
    _git("add", "-A", cwd=wd)
    _git("commit", "-qm", "wrong phase", cwd=wd)
    pre_head = _git("rev-parse", "HEAD", cwd=wd).stdout.strip()
    authorized, evidence = approval_authorizes_tree(
        wd, "relabel_gate_test", "scope", tree, pre_head=pre_head
    )
    assert authorized is False
    assert evidence["failed_checks"] == ["phase"]

    # (6) no date → refused
    (ap / "scope_tree_reuse.md").write_text(_approval_text(tree, date=""))
    _git("add", "-A", cwd=wd)
    _git("commit", "-qm", "no date", cwd=wd)
    pre_head = _git("rev-parse", "HEAD", cwd=wd).stdout.strip()
    authorized, evidence = approval_authorizes_tree(
        wd, "relabel_gate_test", "scope", tree, pre_head=pre_head
    )
    assert authorized is False
    assert evidence["failed_checks"] == ["date"]


def test_approval_without_pre_head_is_refused(tmp_path):
    """With no committed pre-head, no approval can have been committed BEFORE the phase — the
    escape is structurally unreachable on a fresh worktree (the operator must commit the
    approval before launching the run, which always yields a pre-head)."""
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    _git("commit", "-q", "--allow-empty", "-m", "seed", cwd=wd)
    ap = wd / "approvals" / "relabel_gate_test"
    ap.mkdir(parents=True)
    (ap / "scope_tree_reuse.md").write_text(_approval_text("0" * 40))
    _git("add", "-A", cwd=wd)
    _git("commit", "-qm", "approval", cwd=wd)
    tree = _git("rev-parse", "HEAD^{tree}", cwd=wd).stdout.strip()
    authorized, evidence = approval_authorizes_tree(
        wd, "relabel_gate_test", "scope", tree, pre_head=""
    )
    assert authorized is False
    assert evidence["failed_checks"] == ["committed_before_phase"]


# ── off-switches and the runner's own commit path ────────────────────────────


def test_gate_off_for_test_phases(tmp_path):
    """The gate runs for agent phases only — a ``kind: test`` phase never consults the ledger
    (mirrors the deploy/commit gates' ``kind != "test"`` guard)."""
    spec = _minimal_spec(tmp_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    _git("commit", "-q", "--allow-empty", "-m", "seed", cwd=wd)
    ledger = tmp_path / "discarded_trees.jsonl"

    def agent(prompt, *, model, backend, workdir, **kwargs):
        return _fake_agent()

    result = run_workflow(
        spec, goal="g", model="m", workdir=wd, run_agentic_fn=agent,
        discarded_trees_ledger=ledger,
    )
    assert result.phases[0].status == "ok"
    assert result.phases[0].relabel_gate is None


def test_runner_own_git_commit_of_genuine_work_never_fires(tmp_path):
    """The runner's own ``_git_commit`` path is exempt by construction: committing a phase's
    genuine work product (a tree never recorded as discarded) does not consult the ledger and
    the gate stays silent — the exemption is the absence of any tree match, not a carve-out."""
    spec = _minimal_spec(tmp_path)
    wd = tmp_path / "wd"
    wd.mkdir()
    _git_init(wd)
    _git("commit", "-q", "--allow-empty", "-m", "seed", cwd=wd)
    ledger = tmp_path / "discarded_trees.jsonl"

    def agent(prompt, *, model, backend, workdir, **kwargs):
        (Path(workdir) / "docs").mkdir(exist_ok=True)
        (Path(workdir) / "docs" / "scope.md").write_text("fresh work product")
        return _fake_agent()

    result = run_workflow(
        spec, goal="g", model="m", workdir=wd, run_agentic_fn=agent,
        discarded_trees_ledger=ledger,
    )
    assert result.phases[0].status == "ok"
    assert result.phases[0].relabel_gate is None
    assert result.phases[0].commit_hash  # the runner's own commit was made


# ── CLI + script surfaces ────────────────────────────────────────────────────


def test_cli_resolves_workflow_discard_tree():
    from agentic_dynamics import cli

    script, rest = cli._resolve(["workflow", "discard-tree", "--spec", "x"])
    assert script == "record_discarded_tree.py"
    assert rest == ["--spec", "x"]
    assert (cli._SCRIPTS_DIR / script).exists()


def test_discard_tree_script_imports_and_runs_help():
    import sys

    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "record_discarded_tree.py"), "--help"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "discarded tree" in result.stdout
    assert "--spec" in result.stdout and "--workdir" in result.stdout


def test_discard_tree_script_records_a_real_discard(tmp_path):
    """The full CLI (not just the library): one invocation records the worktree's tree onto a
    ledger the gate reads back."""
    import sys

    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / "work.txt").write_text("about to be discarded")
    _git_init(wd)
    _git("add", "-A", cwd=wd)
    _git("commit", "-qm", "attempt A", cwd=wd)
    ledger = tmp_path / "discarded_trees.jsonl"

    result = subprocess.run(
        [
            sys.executable, str(REPO / "scripts" / "record_discarded_tree.py"),
            "--spec", "relabel_gate_test", "--workdir", str(wd), "--ledger", str(ledger),
        ],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "[discard-tree] recorded" in result.stdout
    tree = _git("rev-parse", "HEAD^{tree}", cwd=wd).stdout.strip()
    assert tree in result.stdout
    entries = json.loads(Path(ledger).read_text().splitlines()[0])
    assert entries["tree_hash"] == tree
    assert entries["spec"] == "relabel_gate_test"
