"""Opencode agentic invoke — spawn automode sessions and capture full traces.

Replaces raw API calls with real agentic execution: opencode thinks,
writes files, runs tests, iterates on failures. Captures the complete
tool-call trace, token usage, and test results.

This is the measurement layer the instrument was designed for.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentic_dynamics.control.live import make_publisher
from agentic_dynamics.core.cost_provenance import (
    METHOD_TOKEN_PRICE_TABLE,
    CostObservation,
    CostSource,
    resolve_cost_observation,
)
from agentic_dynamics.core.streaming import stream_subprocess
from agentic_dynamics.measurement.efficiency import compute_cost_estimate

# Resolve opencode binary: env override or default ~/.opencode/bin/opencode
_OPENCODE_BIN = os.environ.get("OPENCODE_BIN", "")
if _OPENCODE_BIN:
    OPENCODE_BIN = _OPENCODE_BIN
elif Path.home().exists():
    OPENCODE_BIN = str(Path.home() / ".opencode/bin/opencode")
else:
    OPENCODE_BIN = "opencode"  # fall back to $PATH


logger = logging.getLogger(__name__)

#: Environment override for the workdir snapshot cap. ``_list_files`` walks a directory
#: hashing every file for before/after change detection; an unbounded tree (a real workdir
#: observed at 1.33M files ground for minutes before the model was ever invoked) turns that
#: bookkeeping into a silent hang. Above this many files the walk stops and returns a
#: :class:`SnapshotSkipped` sentinel instead of an unbounded (and incomplete) dict.
SNAPSHOT_CAP_ENV = "FINOPS_ADAPTER_MAX_SNAPSHOT_FILES"
DEFAULT_SNAPSHOT_MAX_FILES = 50_000


@dataclass(frozen=True)
class SnapshotSkipped:
    """Returned by :func:`_list_files` when a workdir exceeds the snapshot cap.

    Deliberately NOT a ``dict`` (and so distinguishable from a real empty snapshot ``{}``):
    a caller that read a capped walk as "no files" would report "no changes" for a turn that
    may have rewritten the entire tree. ``observed`` is the file count seen when the walk
    stopped (``> cap``); ``cap`` is the configured limit.
    """

    observed: int
    cap: int


class WorkdirDiff(tuple):
    """The changed set ``(created, modified)`` plus HOW it was determined.

    Subclasses ``tuple`` so the historical ``created, modified = _diff_workdir(...)``
    unpacking contract is preserved exactly; ``detection`` carries the provenance the
    consumers need to avoid reporting a skipped snapshot as "no changes":

    ``"hashed"``
        The full byte-level before/after snapshot compared cleanly.
    ``"git_status"``
        The snapshot was skipped; the changed set came from ``git status --porcelain``.
    ``"unavailable"``
        The snapshot was skipped AND git could not answer — the (empty) lists are NOT
        evidence of "no changes".
    """

    def __new__(
        cls,
        created: list[str],
        modified: list[str],
        detection: str = "hashed",
        observed: int | None = None,
        cap: int | None = None,
    ) -> WorkdirDiff:
        obj = super().__new__(cls, (list(created), list(modified)))
        # A tuple subclass gains a ``__dict__`` when no ``__slots__`` is declared; these
        # attributes are the provenance the two-element tuple cannot carry.
        obj.detection = detection
        obj.observed = observed
        obj.cap = cap
        return obj

    @property
    def created(self) -> list[str]:
        return self[0]

    @property
    def modified(self) -> list[str]:
        return self[1]


@dataclass
class AgenticResult:
    """Complete result of an agentic opencode session."""

    # Session
    run_id: str = ""
    task: str = ""
    model: str = ""
    workdir: str = ""
    session_id: str = ""
    exit_code: int = 0
    duration_s: float = 0.0
    error: str = ""

    # Output
    final_response: str = ""
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)

    #: How ``files_created``/``files_modified`` were derived (see :class:`WorkdirDiff`).
    #: ``"hashed"`` is the full before/after snapshot; ``"git_status"`` means the snapshot
    #: was skipped (tree above FINOPS_ADAPTER_MAX_SNAPSHOT_FILES) and the changed set came
    #: from git; ``"unavailable"`` means the snapshot was skipped AND git could not answer,
    #: so the (empty) lists must NOT be read as "no changes". Default preserves the
    #: historical reading for callers that never look at this field.
    change_detection: str = "hashed"

    # Tool call trace
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    total_tool_calls: int = 0
    thinking_steps: int = 0

    # Compounding effects
    retry_loops: int = 0  # how many times did it retry?
    iteration_depth: int = 0  # max depth of tool call chains
    error_count: int = 0  # tool call errors encountered

    # Test results
    tests_passed: int = 0
    tests_total: int = 0
    test_output: str = ""

    # Token usage
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0

    # Whether the backend reported per-step token usage in the transcript. Set by the JSONL
    # parser when it sees a step_finish/usage event carrying a tokens dict — the signal that
    # ``prompt_tokens``/``completion_tokens`` are measured (possibly 0) rather than absent.
    # ``False`` means the session never reached a model call (or the backend reported no
    # usage): the in/out split is coverage-not-available, distinct from a measured zero.
    usage_reported: bool = False

    # Token split — the completion/output stream is partitioned into the "answer"
    # (tokens spent writing the deliverable via tool calls) and "explanation"
    # (tokens spent on prose narration). This is the decomposition the
    # Explanation Tax (silent vs verbose mode) needs. Invariant:
    # answer_tokens + explanation_tokens == completion_tokens.
    answer_tokens: int = 0
    explanation_tokens: int = 0

    # Cache (context tokens not re-sent to provider — "free" reads)
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    # Effective context throughput (billable + cached = total context footprint)
    context_tokens: int = 0

    @property
    def cache_hit_rate(self) -> float:
        """Fraction of context served from cache (0.0–1.0)."""
        total_context = self.total_tokens + self.cache_read_tokens
        if total_context == 0:
            return 0.0
        return self.cache_read_tokens / total_context

    # ── Cost, and where the number came from ────────────────────────────────────────────
    #
    # ``estimated_cost_usd`` keeps its name, type and default so every existing consumer
    # (efficiency, the game report, the lab books, sync_data) is unaffected. The three fields
    # beside it are what phase 3 adds: they say whether that float is a measurement, a
    # local estimate, or a placeholder standing in for a figure nobody ever reported.
    #
    # Read them together:
    #   cost_source=METERED,   reported_cost_usd=0.0   → the provider metered a real $0
    #   cost_source=UNKNOWN,   reported_cost_usd=None  → nobody reported anything; NOT $0
    #   cost_source=ESTIMATED, reported_cost_usd=0.0   → a placeholder zero we declined to
    #                                                    believe (tokens were spent), priced
    #                                                    from the token table instead
    # Before this phase all three arrived downstream as the single float 0.0 — the audit's
    # five-state collapse. See ``core.cost_provenance``.

    #: The figure to bill/report. Kept a plain float (never ``None``) for consumer
    #: compatibility; consult :attr:`cost_source` before trusting a ``0.0``.
    estimated_cost_usd: float = 0.0

    #: Provenance of :attr:`estimated_cost_usd`. Defaults to ``UNKNOWN``: a freshly
    #: constructed result has measured nothing, and the default must not assert otherwise.
    cost_source: CostSource = CostSource.UNKNOWN

    #: How the figure was derived when :attr:`cost_source` is ``ESTIMATED``/``RECONCILED``
    #: (a ``core.cost_provenance.ESTIMATION_METHODS`` member); ``None`` otherwise.
    estimation_method: str | None = None

    #: What the backend itself reported, verbatim and unrepaired — ``None`` when it reported
    #: no cost at all, ``0.0`` when it reported a zero. This is the field that keeps a
    #: provider-reported zero distinguishable from a missing cost.
    reported_cost_usd: float | None = None

    @property
    def cost_observation(self) -> CostObservation:
        """The cost + its provenance as one value object (the settlement step's input)."""
        return CostObservation(
            cost_usd=None if self.cost_source is CostSource.UNKNOWN else self.estimated_cost_usd,
            source=self.cost_source,
            estimation_method=self.estimation_method,
            reported_cost_usd=self.reported_cost_usd,
        )

    @property
    def cost_is_trusted(self) -> bool:
        """True when this run's cost may back a real-dollar reservation (never ``UNKNOWN``)."""
        return self.cost_observation.is_trusted

    def apply_cost_observation(self, observation: CostObservation) -> None:
        """Write a resolved observation onto the result — the adapters' single cost writer.

        Both adapters (and the settlement step) go through here so the four fields can never
        drift out of agreement. ``estimated_cost_usd`` takes ``0.0`` for an ``UNKNOWN``
        observation purely to preserve the field's float contract; ``cost_source`` is what
        says that zero means "not measured".
        """
        self.estimated_cost_usd = observation.billable_usd
        self.cost_source = observation.source
        self.estimation_method = observation.estimation_method
        self.reported_cost_usd = observation.reported_cost_usd

    # Raw session transcript (JSONL from opencode stdout)
    raw_transcript: str = ""

    @property
    def correctness(self) -> float:
        if self.tests_total == 0:
            return 0.0
        return self.tests_passed / self.tests_total

    @property
    def confidence(self) -> float | None:
        """Per-attempt execution-confidence signal, tagged [H].

        Derivation (documented heuristic — NOT the model's self-reported pass/fail):
          1. If the session errored (non-empty ``error``), confidence is 0.0.
          2. Else if any tests ran, confidence is measured correctness
             (``tests_passed / tests_total``) — an outcome-grounded signal.
          3. Else confidence is the tool-call success fraction
             (``1 - error_count / total_tool_calls``) — did the agent's actions
             succeed without retry/error churn?
          4. With no signal at all (no error, no tests, no tool calls), ``None``.

        This is the ``confidence`` the ``model_cascade``/``dynamics`` control arms
        consume. It tracks *outcome* (correctness / action success), not narration:
        a model that narrates "I'm confident" while failing tests gets 0.0. A
        property (not a stored field) so it always reflects the final run state —
        ``error`` is assigned after the transcript is parsed.
        """
        if self.error:
            return 0.0
        if self.tests_total > 0:
            return round(self.tests_passed / self.tests_total, 4)
        if self.total_tool_calls > 0:
            ok_calls = max(self.total_tool_calls - self.error_count, 0)
            return round(ok_calls / self.total_tool_calls, 4)
        return None

    @property
    def text(self) -> str:
        return self.final_response

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and len(self.error) == 0

    # Experiment metadata
    thinking_effort: str = ""
    thinking_budget_tokens: int = 0


def _build_standardized_prompt(
    prompt: str,
    thinking_budget_tokens: int = 0,
    output_token_limit: int = 0,
    enforce_pytest: bool = True,
    silent_mode: bool | None = None,
) -> str:
    """Inject standardized constraints into the prompt for apples-to-apples comparison.

    This ensures every model gets the same formatting constraints regardless of
    training regime. The model can still choose how to allocate tokens — but the
    output format and reporting requirements are standardized.

    Args:
        prompt: Original task prompt.
        thinking_budget_tokens: Maximum thinking/reasoning tokens. 0 = no limit.
        output_token_limit: Maximum output tokens. 0 = no limit.
        enforce_pytest: Require pytest execution and pass/fail report.
        silent_mode: If True, suppress docstrings/comments/explanation.
                     If False, explicitly allow verbosity.
                     If None (default), model uses natural style — we measure the gap.
    """
    header = "[STANDARDIZED CONSTRAINTS — APPLY TO ALL MODELS]\n"
    if thinking_budget_tokens > 0:
        header += (
            f"- Reasoning budget: {thinking_budget_tokens} tokens maximum for thinking/planning\n"
        )
    if output_token_limit > 0:
        header += f"- Output limit: {output_token_limit} tokens maximum total output\n"
    if silent_mode is not None:
        if silent_mode:
            header += (
                "- IMPLEMENTATION-ONLY MODE: do NOT generate docstrings, comments, or "
                "explanatory prose. Output ONLY the working code. Optimize for token efficiency.\n"
            )
        else:
            header += (
                "- VERBOSE MODE: include docstrings, inline comments, and brief reasoning "
                "for every design decision. Optimize for readability and maintainability.\n"
            )
    if enforce_pytest:
        header += (
            "- Write ALL code files. Run pytest. Fix failures until all tests pass.\n"
            "- At the END of your response, state EXACTLY on one line: "
            '"TESTS: N passed, M failed"\n'
        )
    return header + "\n" + prompt


# Thinking effort → opencode --variant mapping
THINKING_VARIANTS = {
    "minimal": "minimal",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "max": "max",
    "default": "default",
}


def run_opencode_agentic(
    prompt: str,
    *,
    model: str = "deepseek/deepseek-v4-pro",
    thinking_effort: str | None = None,
    thinking_budget_tokens: int = 0,
    output_token_limit: int = 0,
    silent_mode: bool | None = None,
    standardize: bool = True,
    enforce_pytest: bool = True,
    workdir: str | None = None,
    timeout: int = 300,
    session_name: str = "",
    init_git: bool = True,
    on_event: Callable[[dict[str, Any]], None] | None = None,
    transcript_path: str | None = None,
    session_id: str | None = None,
    fork: bool = False,
    watchdog: dict | None = None,
) -> AgenticResult:
    """Spawn an opencode agentic session in an isolated worktree.

    Each run gets its own temp directory with git initialized so the
    model can use version control, branches, and commits. This
    provides full isolation between experiment runs and enables
    measurement of file changes, commits, and branching behavior.

    Args:
        prompt: The task prompt (with or without perturbation).
        model: Model identifier (opencode format: provider/model).
        thinking_effort: Override reasoning effort via --variant (minimal/low/medium/high/max).
        thinking_budget_tokens: Max thinking tokens injected into prompt. 0 = no limit.
        output_token_limit: Max output tokens injected into prompt. 0 = no limit.
        silent_mode: If True, suppress docstrings/comments. If False, require verbosity.
                     If None (default), model uses natural style — we measure the gap.
        standardize: Inject STANDARDIZED CONSTRAINTS header into prompt.
        enforce_pytest: Require pytest execution in standardized header.
        workdir: Working directory. Created if None.
        timeout: Maximum session duration in seconds.
        session_name: Name for the session (logging).
        init_git: Whether to initialize a git repo in the workdir.
        on_event: Optional callback invoked per parsed opencode event. Falls
            back to Redis live publishing (``FINOPS_CELL_ID``) when omitted.
        transcript_path: Optional path for the session JSONL transcript.
            Defaults to ``<workdir>/.instrument/session.jsonl``.
        session_id: When set together with ``fork=True``, resume the workflow by
            forking the given session (``--session <id> --fork``), so the shared
            context prefix is served as provider cache reads.
        fork: Fork from ``session_id`` to reuse its context prefix (cache reads).
        watchdog: Optional kill seam (cap_runner_hardening p1). When given, the
            transcript is ALSO appended live, one event line per step, so an external
            monitor can read the session's last-step age from the file's mtime; and
            ``watchdog["kill"]`` is registered (via ``stream_subprocess``) so the
            monitor can SIGTERM the process group when the phase stalls.

    Returns:
        AgenticResult with complete execution trace.
    """

    t0 = time.monotonic()
    result = AgenticResult(
        run_id=session_name or f"opencode_{int(t0)}", task=prompt, model=model, workdir=workdir
    )
    result.thinking_effort = thinking_effort or "default"
    result.thinking_budget_tokens = thinking_budget_tokens

    # Inject standardized constraints for apples-to-apples comparison
    if standardize and not prompt.startswith("[STANDARDIZED CONSTRAINTS"):
        prompt = _build_standardized_prompt(
            prompt,
            thinking_budget_tokens=thinking_budget_tokens,
            output_token_limit=output_token_limit,
            enforce_pytest=enforce_pytest,
            silent_mode=silent_mode,
        )

    # Create an isolated worktree per run
    if workdir is None:
        workdir = tempfile.mkdtemp(prefix="exp_")
        result.workdir = workdir

    # Initialize git for version control tracking
    if init_git:
        _init_git_workdir(workdir)

    # Store files before for change detection
    files_before = _list_files(workdir)

    cmd = [
        OPENCODE_BIN,
        "run",
        "--model",
        model,
        "--format",
        "json",
        "--auto",
        "--dir",
        workdir,
    ]
    if thinking_effort and thinking_effort in THINKING_VARIANTS:
        cmd.extend(["--variant", THINKING_VARIANTS[thinking_effort]])
    if session_name:
        cmd.extend(["--title", session_name])
    if fork and session_id:
        cmd.extend(["--session", session_id, "--fork"])
    if prompt:
        cmd.append(prompt)

    publisher = make_publisher() if on_event is None else None

    # Live transcript seam (cap_runner_hardening p1): while the phase watchdog is active,
    # append each streamed event line to the transcript file as it arrives, so the file's
    # mtime IS the session's last-step time for the runner's stall monitor. Cheap — one
    # buffered write per step — and only enabled when the seam is present (the default path
    # stays byte-identical: the transcript is written once at the end).
    live_fh = None
    if watchdog is not None:
        live_path = (
            Path(transcript_path)
            if transcript_path
            else Path(workdir) / ".instrument" / "session.jsonl"
        )
        live_path.parent.mkdir(parents=True, exist_ok=True)
        live_fh = live_path.open("a")

    def _on_line(line: str) -> None:
        if live_fh is not None and line.strip():
            live_fh.write(line + "\n")
            live_fh.flush()
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return
        if not isinstance(obj, dict):
            return
        if on_event is not None:
            on_event(obj)
        elif publisher is not None:
            publisher.publish_event(obj)

    on_line = (
        _on_line
        if (on_event is not None or publisher is not None or watchdog is not None)
        else None
    )
    try:
        stream = stream_subprocess(
            cmd, workdir=workdir, timeout=timeout, on_line=on_line, watchdog=watchdog
        )
    finally:
        if live_fh is not None:
            live_fh.close()
    if stream.timed_out:
        result.error = f"Timeout after {timeout}s"
        result.exit_code = -1
    else:
        result.exit_code = stream.exit_code
        result.error = stream.stderr.strip() if stream.exit_code != 0 else ""

    # Store raw transcript for artifact bundling
    result.raw_transcript = stream.stdout

    # Parse JSONL output even on non-zero exit (partial output)
    if stream.stdout:
        _parse_session_output(stream.stdout, result)

    result.session_id = _extract_session_id(stream.stdout)

    # Resolve the cost's PROVENANCE, not just its value. The parser has already recorded a
    # metered figure if the provider reported one; this block supplies the token × price-table
    # fallback for the two cases it cannot settle — a placeholder zero (openai's step_finish
    # carries cost=0) and no cost reporting at all.
    #
    # The old code wrote the fallback straight into ``estimated_cost_usd`` and, when even the
    # fallback was unavailable, left the field at its 0.0 default — indistinguishable from a
    # genuinely free run. Now an unpriceable run ends as ``cost_source=UNKNOWN``, which the
    # admission gate refuses to spend real dollars against.
    if result.cost_source is not CostSource.METERED:
        estimate: float | None = None
        if result.total_tokens > 0:
            provider, _, model_id = model.partition("/")
            try:
                est = compute_cost_estimate(
                    prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens,
                    reasoning_tokens=result.reasoning_tokens,
                    cache_read_tokens=result.cache_read_tokens,
                    cache_write_tokens=result.cache_write_tokens,
                    provider=provider,
                    model=model_id,
                )
                estimate = est["total_cost_usd"]
            except (ValueError, KeyError):
                # No price table for this provider/model. That is an UNKNOWN cost, and the
                # resolver below records it as such rather than as a free run.
                estimate = None
        result.apply_cost_observation(
            resolve_cost_observation(
                reported_cost_usd=result.reported_cost_usd,
                estimated_cost_usd=estimate,
                estimation_method=METHOD_TOKEN_PRICE_TABLE,
                tokens_observed=result.total_tokens > 0 or result.usage_reported,
            )
        )

    result.duration_s = time.monotonic() - t0

    # Detect file changes (filter out venv, pip, pytest cache). ``_diff_workdir`` returns a
    # ``WorkdirDiff`` carrying the detection provenance so a skipped snapshot is never
    # silently reported as "no changes".
    _diff = _diff_workdir(workdir, files_before)
    result.files_created, result.files_modified = _diff
    result.change_detection = _diff.detection

    # Persist session transcript for post-hoc artifact bundling
    if result.raw_transcript:
        out_path = (
            Path(transcript_path)
            if transcript_path
            else Path(workdir) / ".instrument" / "session.jsonl"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result.raw_transcript)

    # Extract final response from the last assistant message
    # (already set during parsing)

    return result


def _init_git_workdir(workdir: str) -> None:
    """Initialize a git repo in the workdir for version-control tracking.

    Idempotent (docs/routing_next_steps.md item 5.2): when the worktree already has history
    (``git rev-parse HEAD`` succeeds), this is a no-op — a killed run's leftover work must not
    be swept into a misnamed "Initial" commit, and resume's ``[workflow] <phase>`` commit
    detection must not be confused. The genuinely-new-repo path initializes, sets the runner
    identity, and only commits when something is actually staged (an empty "Initial" commit is
    skipped).
    """
    has_head = (
        subprocess.run(["git", "rev-parse", "HEAD"], cwd=workdir, capture_output=True).returncode
        == 0
    )
    if has_head:
        return

    subprocess.run(["git", "init"], cwd=workdir, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "experiment@instrument.local"],
        cwd=workdir,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Experiment Runner"], cwd=workdir, capture_output=True
    )
    subprocess.run(["git", "add", "-A"], cwd=workdir, capture_output=True)
    staged = subprocess.run(
        ["git", "status", "--porcelain"], cwd=workdir, capture_output=True, text=True
    )
    if not staged.stdout.strip():
        return
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=workdir, capture_output=True)


#: Directory names whose contents are never part of the changed set (build/test caches,
#: dependency trees, the worktree's own git metadata). Shared by the hashed comparison and
#: the git-status fallback so both paths expose the same shape.
_ARTIFACT_DIRS = (".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", ".git")


def _is_artifact(p: str) -> bool:
    """True when any path segment names an artifact directory (see ``_ARTIFACT_DIRS``)."""
    return any(skip in p.split("/") for skip in _ARTIFACT_DIRS)


def _snapshot_max_files() -> int:
    """Resolve the snapshot cap from the environment, defaulting to 50000.

    A missing, non-integer, or negative override falls back to the default rather than
    crashing a turn — malformed configuration is never allowed to kill a run. ``0`` is
    honored (it disables hashing entirely, useful for tests and pathological trees).
    """
    raw = os.environ.get(SNAPSHOT_CAP_ENV)
    if not raw:
        return DEFAULT_SNAPSHOT_MAX_FILES
    try:
        cap = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_SNAPSHOT_MAX_FILES
    return cap if cap >= 0 else DEFAULT_SNAPSHOT_MAX_FILES


def _diff_workdir(workdir: str, files_before: dict[str, str] | SnapshotSkipped) -> WorkdirDiff:
    """Compute files created/modified relative to a prior snapshot.

    ``files_modified`` is the CHANGED-set (content hash differs), not the
    pre-existing-set: a file that existed before the run with unchanged content is
    untouched, not "modified".

    When EITHER snapshot was skipped (the tree exceeded ``FINOPS_ADAPTER_MAX_SNAPSHOT_FILES``)
    the hashes cannot be compared. Rather than fabricate an empty diff, fall back to
    ``git status --porcelain`` (``detection="git_status"``); when git cannot answer, return
    ``detection="unavailable"`` so the caller never mistakes the empty lists for "no
    changes". Under the cap the returned ``WorkdirDiff`` is byte-identical to the historical
    ``(created, modified)`` tuple.
    """
    if isinstance(files_before, SnapshotSkipped):
        # The before-snapshot already told us the tree is over the cap; do not re-walk it.
        return _diff_workdir_from_git(workdir, observed=files_before.observed, cap=files_before.cap)

    files_after = _list_files(workdir)
    if isinstance(files_after, SnapshotSkipped):
        return _diff_workdir_from_git(workdir, observed=files_after.observed, cap=files_after.cap)

    files_created = sorted(
        f for f in (files_after.keys() - files_before.keys()) if not _is_artifact(f)
    )
    files_modified = sorted(
        f
        for f in (files_after.keys() & files_before.keys())
        if not _is_artifact(f) and files_after[f] != files_before[f]
    )
    return WorkdirDiff(files_created, files_modified, detection="hashed")


def _diff_workdir_from_git(workdir: str, *, observed: int | None, cap: int | None) -> WorkdirDiff:
    """Best-effort changed set from git when the hashed snapshot was skipped.

    ``git status`` is a truthful fallback: it names the worktree entries git considers
    changed without hashing every file. When git is unavailable (not a repo, binary absent,
    or the command fails) the result is ``detection="unavailable"`` — the empty lists are an
    honest "we could not tell", never a claim of "no changes".
    """
    changes = _git_status_changes(workdir)
    if changes is None:
        return WorkdirDiff([], [], detection="unavailable", observed=observed, cap=cap)
    created, modified = changes
    return WorkdirDiff(created, modified, detection="git_status", observed=observed, cap=cap)


def _git_status_changes(workdir: str) -> tuple[list[str], list[str]] | None:
    """Parse ``git status --porcelain`` into (created, modified), or None if unavailable.

    Untracked (``??``) and added (``A``) entries are "created"; every other tracked change
    is "modified"; deletions are omitted (matching the hashed path, which only ever lists
    files that exist after the turn). Artifact directories are filtered so the fallback's
    shape matches the hashed comparison. Any failure (no repo, no git, timeout) yields
    ``None`` — the caller degrades to "change detection unavailable", never an exception.
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None

    created: list[str] = []
    modified: list[str] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        xy, path = line[:2], line[3:]
        if " -> " in path:  # rename/copy: report the destination path
            path = path.split(" -> ", 1)[1]
        path = _unquote_git_path(path)
        if not path or _is_artifact(path):
            continue
        if xy == "??" or "A" in xy:
            created.append(path)
        elif "D" in xy:
            continue
        else:
            modified.append(path)
    return sorted(created), sorted(modified)


def _unquote_git_path(path: str) -> str:
    """Undo git's C-style quoting of paths that contain special characters."""
    if len(path) >= 2 and path.startswith('"') and path.endswith('"'):
        try:
            return json.loads(path)
        except json.JSONDecodeError:
            return path[1:-1]
    return path


def _list_files(dirpath: str) -> dict[str, str] | SnapshotSkipped:
    """Snapshot files in a directory: relative path -> sha256 content hash.

    Walks ``dirpath`` counting files; once the count exceeds
    ``FINOPS_ADAPTER_MAX_SNAPSHOT_FILES`` (default 50000) the walk STOPS without hashing
    further and returns a :class:`SnapshotSkipped` carrying the observed count and the cap.
    The cap bounds an otherwise unbounded walk — a large tree (a real workdir observed at
    1.33M files) would otherwise grind for minutes before the model was invoked, and the
    resulting dict would be too incomplete to compare honestly anyway.

    Below the cap the return value is byte-identical to the historical snapshot: a
    ``{relative_path: sha256}`` dict. A walk that raises is likewise reported as
    ``SnapshotSkipped`` (an unknown snapshot), never as an empty one.
    """
    import hashlib

    cap = _snapshot_max_files()
    observed = 0
    try:
        root = Path(dirpath)
        snapshot: dict[str, str] = {}
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            observed += 1
            if observed > cap:
                logger.warning(
                    "workdir snapshot skipped: %d files > cap (%s)",
                    observed,
                    SNAPSHOT_CAP_ENV,
                )
                return SnapshotSkipped(observed=observed, cap=cap)
            rel = str(p.relative_to(root))
            try:
                digest = hashlib.sha256(p.read_bytes()).hexdigest()
            except OSError:
                digest = ""
            snapshot[rel] = digest
        return snapshot
    except Exception:
        # A failed walk is an UNKNOWN snapshot, not an empty one: returning ``{}`` here (the
        # historical behavior) would make the diff read a broken walk as "the tree is empty".
        # Report it as skipped so the consumer falls back to git / degrades honestly.
        return SnapshotSkipped(observed=observed, cap=cap)


def _extract_session_id(stdout: str) -> str:
    """Extract the sessionID from the first JSONL event that carries one."""
    if not stdout:
        return ""
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        sid = obj.get("sessionID", "")
        if sid:
            return sid
    return ""


def _parse_session_output(stdout: str, result: AgenticResult) -> None:
    """Parse opencode JSONL output to extract structured trace data.

    Opencode output format (v2):
    - {"type":"step_start", "sessionID":..., "part":{"type":"step-start"}}
    - {"type":"tool_use", "part":{"type":"tool","tool":"write|bash|read|edit|grep...",
        "state":{"status":"completed","input":{...},"output":"..."}}}
    - {"type":"text", "part":{"type":"text","text":"..."}}
    - {"type":"step_finish", "part":{"tokens":{"total":...,"input":...,"output":...,"reasoning":...}}}
    """
    tool_calls = []
    final_texts = []
    iteration_depth = 0
    current_depth = 0
    retry_count = 0
    last_was_error = False
    # Positive per-step cost readings — the provider's own meter. Kept separate from
    # ``_reported_any_cost`` because the two answer different questions: "how much?" vs
    # "did the backend report a cost field AT ALL?". Conflating them is precisely how a
    # missing cost became $0.00.
    _step_costs: list[float] = []
    #: True once any step carried a numeric ``cost`` key, INCLUDING an explicit zero.
    _reported_any_cost = False
    # Whether the current step produced tool calls (wrote/edited the deliverable)
    # vs was prose-only. Drives the answer/explanation token split at step_finish.
    step_has_tool = False

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(obj, dict):
            continue

        etype = obj.get("type", "")
        part = obj.get("part", {})
        if not isinstance(part, dict):
            part = {}

        # Tool calls
        if etype == "tool_use":
            step_has_tool = True
            tool_name = part.get("tool", "")
            state = part.get("state", {})
            if not isinstance(state, dict):
                state = {}
            status = state.get("status", "?")
            tool_input = state.get("input", "")
            tool_output = state.get("output", "")
            is_error = status not in ("completed", "success") or (
                "error" in str(tool_output).lower() if tool_output else False
            )

            tool_calls.append(
                {
                    "type": "tool_use",
                    "tool": tool_name,
                    "input": str(tool_input)[:300],
                    "output": str(tool_output)[:300],
                    "status": status,
                    "is_error": is_error,
                }
            )
            current_depth += 1
            iteration_depth = max(iteration_depth, current_depth)
            result.total_tool_calls += 1

            if is_error:
                result.error_count += 1
                if last_was_error:
                    retry_count += 1
                last_was_error = True
            else:
                last_was_error = False

        # Tool result (step_follow variant)
        elif etype in ("tool_result", "step_follow"):
            current_depth = max(0, current_depth - 1)

        # Step boundary — reset the answer/explanation attribution flag. A fresh
        # step starts with no tool activity; the next tool_use (if any) re-marks it.
        elif etype == "step_start":
            step_has_tool = False

        # Model text response
        elif etype == "text":
            text_content = part.get("text", "")
            if text_content:
                final_texts.append(str(text_content))

        # Step finish — accumulate token usage and cost
        elif etype == "step_finish":
            current_depth = max(0, current_depth - 1)
            tokens = part.get("tokens", {})
            # Capture and reset the step's answer/explanation flag before the token
            # dict is read, so a missing tokens dict can't leak the flag into the
            # next step's attribution.
            was_tool_step = step_has_tool
            step_has_tool = False
            if isinstance(tokens, dict):
                # The backend reported usage for this step — the split is measured (even a
                # legitimately zero token count is a real measurement), not absent.
                result.usage_reported = True
                # Token counts are per-step deltas, sum across steps
                result.prompt_tokens += tokens.get("input", 0) or 0
                result.completion_tokens += tokens.get("output", 0) or 0
                result.reasoning_tokens += tokens.get("reasoning", 0) or 0
                # Answer/explanation split [H]: a step that wrote code (tool calls)
                # is counted as "answer"; a prose-only step is "explanation". This
                # is a step-granularity heuristic, not a per-token attribution.
                out_tokens = tokens.get("output", 0) or 0
                if was_tool_step:
                    result.answer_tokens += out_tokens
                else:
                    result.explanation_tokens += out_tokens
                cache = tokens.get("cache", {})
                if isinstance(cache, dict):
                    result.cache_read_tokens += cache.get("read", 0) or 0
                    result.cache_write_tokens += cache.get("write", 0) or 0
                # Total = actionable tokens only (cache is context reuse, not billed)
                result.total_tokens = (
                    result.prompt_tokens + result.completion_tokens + result.reasoning_tokens
                )
                result.context_tokens = result.total_tokens + result.cache_read_tokens
            # Collect cost — format depends on provider.
            # ``cost`` absent entirely and ``cost: 0`` are DIFFERENT observations: opencode
            # emits an explicit zero for providers it does not price (the openai path), and
            # that zero is evidence the backend was asked and had nothing, whereas a missing
            # key is evidence of nothing at all. Sentinel-default the lookup so the two stay
            # apart, and record the zero without letting it into the arithmetic below.
            cost_val = part.get("cost")
            if isinstance(cost_val, (int, float)) and not isinstance(cost_val, bool):
                _reported_any_cost = True
                if cost_val > 0:
                    _step_costs.append(float(cost_val))

        # Parse test output from bash tool results
        if etype == "tool_use" and part.get("tool") == "bash":
            state = part.get("state", {})
            output = state.get("output", "") if isinstance(state, dict) else ""
            if output and (
                "test" in str(output).lower()
                or "pass" in str(output).lower()
                or "fail" in str(output).lower()
            ):
                import re

                if "passed" in str(output).lower():
                    # pytest output: X passed, Y failed
                    m = re.search(r"(\d+)\s+passed", str(output))
                    if m:
                        p = int(m.group(1))
                        mf = re.search(r"(\d+)\s+failed", str(output))
                        f = int(mf.group(1)) if mf else 0
                        result.tests_passed = p
                        result.tests_total = p + f
                result.test_output = str(output)[-500:]

    result.tool_calls = tool_calls
    result.retry_loops = retry_count
    result.iteration_depth = iteration_depth
    result.final_response = "\n".join(final_texts[-3:]) if final_texts else ""

    # Provider cost format detection:
    # - DeepSeek: cost is cumulative per step (always increasing)
    # - OpenAI/Anthropic: cost is a per-step delta (may decrease)
    # If costs never decrease → cumulative, use last value.
    # If any cost is lower than a prior cost → per-step, sum all.
    if _step_costs:
        if all(_step_costs[i] >= _step_costs[i - 1] for i in range(1, len(_step_costs))):
            reported = _step_costs[-1]  # cumulative
        else:
            reported = sum(_step_costs)  # per-step delta
        # A positive reading IS the provider's meter, so the provenance is settled here; the
        # caller's price-table fallback below will not fire (it only runs on 0.0/absent).
        result.apply_cost_observation(
            resolve_cost_observation(reported_cost_usd=reported, tokens_observed=True)
        )
    elif _reported_any_cost:
        # Every step reported a cost, and every one of them was zero. Keep the observation —
        # ``reported_cost_usd=0.0`` is what distinguishes this from "nothing was reported" —
        # and leave the final call to the caller, which knows whether tokens were spent.
        result.reported_cost_usd = 0.0

    # Estimate correctness from test results if not directly parsed
    if result.tests_total == 0 and "passed" in str(result.test_output).lower():
        result.tests_total = max(result.tests_total, 1)
        result.tests_passed = max(result.tests_passed, 1)


def normalize_opencode_event(event: dict, schema_version: int | None = None) -> dict:
    """Normalize an opencode JSONL event to a canonical v1-compatible format.

    Handles two schema versions:
      v1 (historical): flat structure — {"type":"tool","tool":"write","state":{...}},
          {"type":"reasoning","text":"..."}, {"type":"step-finish","tokens":{...}}
      v2 (current): nested structure — {"type":"tool_use","part":{"tool":"write",...}},
          {"type":"step_finish","part":{"tokens":{...}}}, {"type":"text","part":{"text":"..."}}

    Detection: v2 events have a ``part`` key containing nested fields.
    v1 events have top-level ``tool``, ``tokens``, ``text`` fields directly.

    Returns a canonical dict with:
      - ``type``: "reasoning" | "tool" | "text" | "step-finish" | "step-start" |
        "tool_result" | "step_follow"
      - ``_schema``: detected schema version (1 or 2)
      - Top-level fields: ``tool``, ``text``, ``tokens``, ``state`` (flattened from part if v2)
      - ``_raw_part``: original part dict preserved for v2 events (None for v1)
    """
    if not isinstance(event, dict):
        return {"type": "unknown", "_schema": 0, "_error": "not a dict"}

    # Detect schema if not provided
    if schema_version is None:
        etype = event.get("type", "")
        part = event.get("part")
        has_part = isinstance(part, dict)

        # v2 detection: type matches v2 naming convention (tool_use, step_start, etc.)
        # or has a non-empty part dict
        v2_types = {"tool_use", "tool_result", "step_follow", "step_start", "step_finish"}
        if etype in v2_types or (has_part and etype in ("text", "reasoning")):
            schema_version = 2
        else:
            schema_version = 1

    canonical = {"_schema": schema_version, "_raw_part": event.get("part")}

    if schema_version == 2:
        part = event.get("part", {})
        if not isinstance(part, dict):
            part = {}
        etype = event.get("type", "")

        if etype == "tool_use":
            canonical["type"] = "tool"
            canonical["tool"] = part.get("tool", "")
            state = part.get("state", {})
            canonical["state"] = state if isinstance(state, dict) else {}
            canonical["callID"] = part.get("callID", "")

        elif etype == "step_finish":
            canonical["type"] = "step-finish"
            tokens = part.get("tokens", {})
            canonical["tokens"] = tokens if isinstance(tokens, dict) else {}
            # ``cost`` keeps its float contract (``scripts/analyze_trajectories.py`` sums it
            # unconditionally), so this projection's ARITHMETIC is unchanged. ``cost_reported``
            # is the additive provenance bit: False means the event carried no cost field, so
            # the 0.0 beside it is a placeholder rather than a measured zero. Without it, a
            # transcript that never reported a cost aggregates into ``total_cost: 0.0`` and
            # reads as a free session — the same five-state collapse, on the post-hoc surface.
            cost = part.get("cost")
            reported = isinstance(cost, (int, float)) and not isinstance(cost, bool)
            canonical["cost"] = float(cost) if reported else 0.0
            canonical["cost_reported"] = reported

        elif etype == "text":
            canonical["type"] = "text"
            canonical["text"] = str(part.get("text", ""))

        elif etype == "reasoning":
            canonical["type"] = "reasoning"
            canonical["text"] = str(part.get("text", ""))

        elif etype == "step_start":
            canonical["type"] = "step-start"

        elif etype in ("tool_result", "step_follow"):
            canonical["type"] = etype

        else:
            canonical["type"] = etype

    else:
        # v1 — already flat, keep as-is
        etype = event.get("type", "")

        # Normalize type names for consistency
        type_map = {
            "tool": "tool",
            "reasoning": "reasoning",
            "text": "text",
            "step-finish": "step-finish",
            "step-start": "step-start",
            "tool_result": "tool_result",
            "step_follow": "step_follow",
        }
        canonical["type"] = type_map.get(etype, etype)

        if etype in ("reasoning", "text"):
            canonical["text"] = str(event.get("text", ""))
        if etype == "tool":
            canonical["tool"] = event.get("tool", "")
            state = event.get("state", {})
            canonical["state"] = state if isinstance(state, dict) else {}
        if etype == "step-finish":
            tokens = event.get("tokens", {})
            canonical["tokens"] = tokens if isinstance(tokens, dict) else {}

        # Preserve original event metadata
        for k in ("timestamp", "sessionID"):
            if k in event:
                canonical[k] = event[k]

    return canonical
