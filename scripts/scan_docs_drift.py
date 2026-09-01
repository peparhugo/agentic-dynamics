#!/usr/bin/env python3
"""Deterministic docs-drift scanner — the instrument of the ``automatic_docs_sync`` rail (p1).

WHAT THIS IS
------------
The repository's *derived* surfaces (``.opencode/``, ``.claude/``, ``agent_config/system_snapshot.md``,
``experiments/specs/STATUS.md``) already regenerate from their sources and are guarded against
renderer drift. What drifts *silently* is the **source-doc content**: an ``ARCHITECTURE.md`` count
that no longer matches the tree, a skill that documents 7 CLI flags when the runner grew to 24, a
``file:line`` anchor that dangles after the code it pointed at was refactored away.

This scanner turns "are the docs current?" into a **measured, reproducible number**. Every check
below re-derives a claim's truth from the code and compares it to what a source doc asserts.

THE ZERO-MODEL-CALL GUARANTEE (spec hard rule 1)
------------------------------------------------
This module imports no network client and invokes no model. Its only subprocess is ``git`` (for
tracked-file listings at a pinned SHA). Every finding is therefore a *reproducible statement* —
a file comparison or a command output — not an opinion. Each finding carries a ``basis`` field
naming exactly how to re-derive it by hand.

THE ANCHORED-CLAIM DISCIPLINE (spec hard rule 4)
-------------------------------------------------
The docs' own convention (``ARCHITECTURE.md`` provenance header) is that a claim carries ``[C]``
(computed) or ``[M]`` (measured) plus, where internal, a ``file:line`` anchor. This scanner
verifies claims **at their anchor**, which is the single most important semantic here:

    A claim pinned to a SHA is verified AT THAT SHA, not at HEAD.

``ARCHITECTURE.md`` §1 asserts "107 tracked Python modules at the pinned SHA ``806c0d34…``". At
HEAD that number is 115 — but the claim never said HEAD. Evaluated at its own anchor with its own
stated basis it reproduces exactly, so it is ``current``. A scanner that compared it to HEAD would
cry wolf on a correctly-written claim, and the spec's stated risk is precisely that a false drift
flag burns trust.

SCOPE RULE — SOURCE DOCS, NOT DERIVED SURFACES
-----------------------------------------------
Only hand-authored documents are scanned. Derived surfaces are excluded (``EXCLUDED_PREFIXES``)
because they have their own regeneration rail: flagging them here would double-report a class of
drift that ``agentic-dynamics surfaces sync`` already fixes mechanically, and would make the score
oscillate with regeneration timing rather than with real doc quality.

THE SEVEN AXES
--------------
====================  ====================================================================
axis                  what it verifies
====================  ====================================================================
``cli_surface``       (a) every flag / subcommand a source doc documents resolves in code
``module_inventory``  (b) ARCHITECTURE.md's plane + module counts match the tree at the SHA
``spec_lifecycle``    (c) documented spec counts match ``experiments/specs/index.json``
``status_vocabulary`` (d) every doc carries enforced status frontmatter (doc-lifecycle guard)
``anchor_integrity``  (e) every ``file:line`` anchor resolves to a file that has that line
``manifest_counts``   (f) ``scripts/CONTEXT.md``'s manifest covers ``scripts/`` with no orphans
``fast_path``         (g) the fast-path command + budget that ``scripts/CONTEXT.md`` documents
                           match the code (``scripts/test_fast.sh`` + the gate's
                           ``FAST_BUDGET_SECONDS`` in ``tests/test_fast_path_gate.py``) and the
                           ``fast``-marked subset is non-empty
====================  ====================================================================

STATUS VOCABULARY
-----------------
``current``  the claim reproduces against the code.
``stale``    the claim's referent EXISTS but disagrees — a wrong count, a flag argparse does not
             declare, an anchor pointing past a file's end. This is the dangerous class: the doc
             reads as authoritative and is wrong.
``missing``  the claim's referent is ABSENT — a cited file that does not exist, a doc with no
             status frontmatter, a script in no manifest bucket.

The drift score is ``stale + missing`` counted per axis. Zero is a clean tree.

USAGE
-----
    python scripts/scan_docs_drift.py                        # human summary, exit 0
    python scripts/scan_docs_drift.py --json report.json     # write the machine-readable report
    python scripts/scan_docs_drift.py --fail-on-drift        # exit 1 when the score is non-zero
    python scripts/scan_docs_drift.py --check anchor_integrity   # one axis only
    python scripts/scan_docs_drift.py --include-current      # serialize every check row, not
                                                             # just the findings

Exit codes: 0 = scan completed (see the score), 1 = drift found AND ``--fail-on-drift`` given,
2 = the scan itself could not run (a malformed manifest, an unreadable index).
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────────────────────
# Paths and scope
# ─────────────────────────────────────────────────────────────────────────────────────────────

#: Repository root — this file lives at ``<root>/scripts/scan_docs_drift.py``.
ROOT = Path(__file__).resolve().parent.parent

#: The seven axis identifiers, in the order the spec lists them (a)–(g). Used for stable report
#: ordering and for ``--check`` validation.
AXES = (
    "cli_surface",
    "module_inventory",
    "spec_lifecycle",
    "status_vocabulary",
    "anchor_integrity",
    "manifest_counts",
    "fast_path",
)

#: Path prefixes whose documents are DERIVED, not authored. Excluded per the scope rule above:
#: these regenerate from ``agent_config/`` + live state via ``scripts/_gen_instructions.py`` and
#: ``scripts/sync_surfaces.py``, and are already covered by the renderer-drift guards
#: (``tests/test_agent_config_render.py``). Scanning them would report regeneration lag as doc
#: drift — a different problem with a different owner.
EXCLUDED_PREFIXES = (
    ".claude/",
    ".opencode/",
    "agent_config/system_snapshot.md",  # the L0 game board — regenerated by `surfaces snapshot`
    "experiments/specs/STATUS.md",      # regenerated by `scripts/spec_status.py`
)


def _excluded(rel: str) -> bool:
    """True when ``rel`` (a repo-relative POSIX path) is a derived surface, not a source doc."""
    return any(rel.startswith(p) for p in EXCLUDED_PREFIXES)


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Check:
    """One verified claim.

    Attributes:
        check_id: Stable, human-readable identifier — ``<axis>/<kind>/<subject>``. Stable across
            runs so a report diff shows what changed rather than a reshuffled list.
        axis: One of :data:`AXES`.
        claim: What the source doc asserts, quoted or summarised.
        code_truth: What re-deriving the claim from the code actually yields.
        status: ``current`` | ``stale`` | ``missing``.
        basis: The reproducible derivation — a shell command or an explicit file comparison.
            This is the anchored-claim discipline: a finding a reader cannot re-derive is prose.
        source: Repo-relative path of the document making the claim (``:line`` when known).
    """

    check_id: str
    axis: str
    claim: str
    code_truth: str
    status: str
    basis: str
    source: str

    @property
    def is_finding(self) -> bool:
        """A finding is any check that did not come back ``current``."""
        return self.status != "current"


@dataclass
class DriftReport:
    """The full scan result: an inventory of checks plus the machine-readable drift score."""

    checks: list[Check] = field(default_factory=list)
    #: Axes that were requested but could not run, with the reason. An axis that cannot run is
    #: NOT silently scored zero — that would read as "clean" when it means "unmeasured".
    errors: dict[str, str] = field(default_factory=dict)

    def add(self, check: Check) -> None:
        self.checks.append(check)

    @property
    def findings(self) -> list[Check]:
        """Every non-``current`` check, ordered by axis then id for a stable diff."""
        order = {a: i for i, a in enumerate(AXES)}
        return sorted(
            (c for c in self.checks if c.is_finding),
            key=lambda c: (order.get(c.axis, 99), c.check_id),
        )

    def score(self) -> dict:
        """The machine-readable drift score: stale + missing counts per axis, plus totals.

        A per-axis breakdown (rather than one number) is what makes the score *actionable*: the
        watchdog (p2) and the proposal gate (p3) can threshold on an axis, and a reader can see
        at a glance whether the drift is anchors, counts, or CLI surface.
        """
        per_axis: dict[str, dict[str, int]] = {
            a: {"current": 0, "stale": 0, "missing": 0, "checked": 0} for a in AXES
        }
        for c in self.checks:
            bucket = per_axis.setdefault(
                c.axis, {"current": 0, "stale": 0, "missing": 0, "checked": 0}
            )
            bucket[c.status] = bucket.get(c.status, 0) + 1
            bucket["checked"] += 1
        for bucket in per_axis.values():
            bucket["drift"] = bucket["stale"] + bucket["missing"]
        return {
            "total_checked": len(self.checks),
            "total_current": sum(1 for c in self.checks if c.status == "current"),
            "total_stale": sum(1 for c in self.checks if c.status == "stale"),
            "total_missing": sum(1 for c in self.checks if c.status == "missing"),
            "drift": sum(1 for c in self.checks if c.is_finding),
            "per_axis": per_axis,
            "axes_errored": sorted(self.errors),
        }

    def to_json(self, *, include_current: bool = False) -> dict:
        """Serialise to the report shape consumed by the watchdog, the gate, and the portal."""
        rows = self.checks if include_current else self.findings
        return {
            "schema": "docs-drift/v1",
            "root": str(ROOT),
            "git_sha": _git_head(),
            "score": self.score(),
            "errors": self.errors,
            "findings": [asdict(c) for c in rows],
            "includes_current_rows": include_current,
        }


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Small deterministic helpers
# ─────────────────────────────────────────────────────────────────────────────────────────────


def _git(*args: str) -> str:
    """Run a read-only git command at :data:`ROOT` and return stdout (empty string on failure).

    The scanner's only subprocess. Read-only by construction — the callers pass ``ls-files`` /
    ``ls-tree`` / ``rev-parse`` only.
    """
    try:
        out = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False, timeout=60
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout if out.returncode == 0 else ""


def _git_head() -> str:
    """The current HEAD SHA, or ``"unknown"`` outside a checkout — recorded in the report."""
    return _git("rev-parse", "HEAD").strip() or "unknown"


def _read(path: Path) -> str:
    """Read a text file tolerantly — a stray encoding error must not abort a whole scan."""
    return path.read_text(encoding="utf-8", errors="replace")


def _line_count(path: Path) -> int:
    """Number of lines in ``path`` — the quantity an anchor's line number is checked against."""
    return len(_read(path).splitlines())


def _front_matter(path: Path) -> dict[str, str]:
    """Parse the leading ``---`` YAML front-matter block into a flat dict.

    Deliberately a mirror of ``tests/test_doc_lifecycle.py::_front_matter`` rather than a YAML
    dependency: the scanner must agree with the guard exactly, and the guard is the contract.
    Returns ``{}`` when the file does not open with ``---``.
    """
    lines = _read(path).splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta


def _norm_ws(text: str) -> str:
    """Collapse all runs of whitespace to single spaces.

    Source docs hard-wrap at 100 characters, so a single claim ("107 tracked Python modules at the
    pinned SHA …") routinely spans two lines. Normalising first lets one regex match the claim
    regardless of where the author's wrap fell — the check tracks meaning, not line breaks.
    """
    return re.sub(r"\s+", " ", text)


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Axis (a) — CLI surface
# ─────────────────────────────────────────────────────────────────────────────────────────────
#
# Two sub-checks: documented FLAGS resolve in the backing script, and documented CLI SUBCOMMANDS
# resolve through the real dispatcher.
#
# DESIGN NOTE — why a declared surface table instead of "scan every code block":
# A generic scanner that attributed every ``--flag`` in any block mentioning a script would
# mis-fire immediately. The run-workflow skill's containerised example reads
# ``docker-compose … run --rm workflow-runner python3 scripts/run_workflow.py --orchestrator …``
# — ``--rm`` belongs to docker, not to the runner, and a naive scanner would report it as a
# phantom flag. Crying wolf is the spec's named failure mode, so the surfaces a doc *claims* are
# declared explicitly below. The table is itself the "inventory of anchorable claims" hard rule 4
# requires: each row names its doc, its target, and its extraction rule.

#: Documented CLI surfaces: the places a source doc enumerates a script's flags.
#:
#: Keys:
#:   ``id``       stable identifier used in ``check_id``
#:   ``doc``      repo-relative source document making the claim
#:   ``target``   repo-relative backing script the flags belong to
#:   ``mode``     extraction rule (see ``_extract_documented_flags``)
#:   ``marker``   (``marker_block`` only) substring identifying the block's opening line
#:   ``complete`` True when the doc claims to enumerate the WHOLE flag set. Only then is the
#:                reverse direction (code flag absent from the doc) a finding — otherwise a
#:                partial reference block would be reported as drift for being a summary, which
#:                it is entitled to be.
DOCUMENTED_CLI_SURFACES: tuple[dict, ...] = (
    {
        # The skill's flag reference block: lines that BEGIN with the flag being documented.
        "id": "run_workflow_skill",
        "doc": "agent_config/skills/run-workflow.md",
        "target": "scripts/run_workflow.py",
        "mode": "leading_flag_lines",
        "complete": False,  # a semantics guide; it may legitimately omit niche flags
    },
    {
        # mental-model.md line 433 opens with the literal words "full CLI:" — the doc asserts
        # completeness, so both directions are checked here.
        "id": "mental_model_full_cli",
        "doc": "agent_config/mental-model.md",
        "target": "scripts/run_workflow.py",
        "mode": "marker_block",
        "marker": "full CLI: scripts/run_workflow.py",
        "complete": True,
    },
)

#: Documents whose ``agentic-dynamics <group> <verb>`` trees are checked against the real
#: dispatcher. These are the hand-authored CLI maps; the rendered copies under ``.claude/`` and
#: ``.opencode/`` are excluded by the scope rule.
DOCUMENTED_CLI_TREES: tuple[str, ...] = (
    "agent_config/mental-model.md",
    "agent_config/rules.md",
    "AGENTS.md",
)

#: NOTE (coverage, recorded rather than silently omitted): ``scripts/fleet/*`` tools are cited in
#: the source docs by PATH and ``file:line`` anchor only — no source doc enumerates their flags in
#: a block, so there is no flag claim to verify and this table has no fleet row. Fleet doc
#: accuracy is therefore covered by the ``anchor_integrity`` axis, not by ``cli_surface``. Adding
#: a fleet flag block to a doc means adding a row here; the surface inventory in the report makes
#: the current coverage explicit so "no fleet row" never reads as "fleet passed".
FLEET_FLAG_SURFACES_DOCUMENTED = 0


def _argparse_flags(script: Path) -> set[str]:
    """Flags the script DECLARES via ``argparse.add_argument("--flag", …)``.

    Parsed statically with :mod:`ast` rather than by executing ``--help``. Static parsing is
    deterministic, has no import side effects (several scripts connect to Redis at import time),
    and cannot hang — all properties the scan needs. This is the *precise* set, used for the
    completeness (reverse) direction.
    """
    flags: set[str] = set()
    try:
        tree = ast.parse(_read(script))
    except (SyntaxError, ValueError):
        return flags
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "add_argument"):
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if arg.value.startswith("--"):
                    flags.add(arg.value)
    return flags


def _literal_flags(script: Path) -> set[str]:
    """Every ``--flag``-shaped string literal anywhere in the script.

    Not all scripts use argparse. ``scripts/enqueue.py``, for instance, hand-rolls its parsing::

        missing_only = "--missing-only" in sys.argv

    An argparse-only extractor would report ``--missing-only`` as a phantom flag — a false
    positive on a flag that genuinely works. Collecting all flag-shaped literals covers every
    parsing idiom (argparse, ``sys.argv`` scanning, dict-driven dispatch).

    The trade-off is deliberate and one-directional: this set is *permissive*, so it is used only
    for the "documented flag must exist" direction, where over-acceptance costs a missed finding
    rather than a false alarm. The stricter :func:`_argparse_flags` drives the reverse direction.
    """
    flags: set[str] = set()
    try:
        tree = ast.parse(_read(script))
    except (SyntaxError, ValueError):
        return flags
    pattern = re.compile(r"^--[a-z0-9][a-z0-9-]*$")
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if pattern.match(node.value):
                flags.add(node.value)
    return flags


#: Matches a long flag token wherever it appears in prose or a code block.
_FLAG_TOKEN = re.compile(r"--[a-z0-9][a-z0-9-]*")


def _extract_documented_flags(doc_text: str, surface: dict) -> dict[str, int]:
    """Extract the flags a surface documents, mapped to the 1-indexed line they appear on.

    Two extraction rules, chosen per surface because doc shapes differ:

    ``leading_flag_lines``
        A line whose first non-space token IS a flag (the skill's reference block, where each
        flag opens its own row). This is the highest-signal rule available: a flag *being
        documented* starts its row, while a flag merely *mentioned* in a sentence does not. That
        distinction is what keeps ``--rm`` in the docker example out of the results.

    ``marker_block``
        A continuation block opened by ``marker`` and closed by ``]`` or the first line that is
        not a comment continuation. Used for mental-model.md's ``# full CLI: …`` comment, which
        lists flags inline across four wrapped lines.
    """
    found: dict[str, int] = {}
    lines = doc_text.splitlines()
    mode = surface["mode"]

    if mode == "leading_flag_lines":
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            match = _FLAG_TOKEN.match(stripped)
            # `match` (anchored at position 0) is the point: the flag must OPEN the line.
            if match:
                found.setdefault(match.group(0), i)
        return found

    if mode == "marker_block":
        marker = surface["marker"]
        in_block = False
        for i, line in enumerate(lines, start=1):
            if not in_block:
                if marker in line:
                    in_block = True
                else:
                    continue
            elif not line.strip().startswith("#"):
                # A continuation line must still be a comment; anything else closes the block.
                break
            for token in _FLAG_TOKEN.findall(line):
                found.setdefault(token, i)
            if "]" in line:
                break  # the bracketed optional-flag list is closed
        return found

    raise ValueError(f"unknown CLI surface extraction mode: {mode!r}")


def _load_cli_resolver():
    """Load ``_resolve`` from the SCANNED tree's ``cli.py``, or None if unavailable.

    Ground truth for a subcommand claim is the real dispatcher, not a re-derived copy of the
    command table: re-implementing the longest-prefix walk here would let the two drift apart —
    precisely the bug class this scanner exists to catch.

    Loaded by file path under a private module name rather than via ``import agentic_dynamics.cli``
    on a mutated ``sys.path``. That import style caches the package in ``sys.modules`` keyed by its
    real name, so scanning one tree would poison every later scan of a different tree in the same
    process (the test suite caught exactly this: a fixture's stub leaked into the real-tree scan).
    ``cli.py`` is a stdlib-only dispatcher, so a standalone file load is faithful.
    """
    cli_path = ROOT / "src" / "agentic_dynamics" / "cli.py"
    if not cli_path.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location("_docs_drift_cli_probe", cli_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return getattr(module, "_resolve", None)
    except Exception:  # pragma: no cover - a malformed cli.py is reported as an errored axis
        return None


def check_cli_surface(report: DriftReport) -> None:
    """Axis (a): documented flags and subcommands resolve in the code."""
    # ── (a1) documented flags resolve in their backing script ────────────────────────────────
    for surface in DOCUMENTED_CLI_SURFACES:
        doc_path = ROOT / surface["doc"]
        target_path = ROOT / surface["target"]
        if not doc_path.is_file() or not target_path.is_file():
            report.errors[f"cli_surface/{surface['id']}"] = (
                f"surface unscannable: doc={surface['doc']} exists={doc_path.is_file()}, "
                f"target={surface['target']} exists={target_path.is_file()}"
            )
            continue

        documented = _extract_documented_flags(_read(doc_path), surface)
        resolvable = _literal_flags(target_path)
        declared = _argparse_flags(target_path)
        basis_cmd = (
            f"python - <<'PY'  # ast scan of {surface['target']} for flag literals\nPY"
        )

        # Forward direction: every documented flag must exist in the target.
        for flag, line_no in sorted(documented.items()):
            ok = flag in resolvable
            report.add(
                Check(
                    check_id=f"cli_surface/{surface['id']}/documented/{flag}",
                    axis="cli_surface",
                    claim=f"{surface['doc']} documents `{flag}` for {surface['target']}",
                    code_truth=(
                        f"{flag} present in {surface['target']}"
                        if ok
                        else f"{flag} NOT found in {surface['target']} "
                        f"(argparse declares {len(declared)} flags)"
                    ),
                    status="current" if ok else "stale",
                    basis=(
                        f"grep -o '\\-\\-[a-z0-9-]*' {surface['target']} | sort -u  "
                        f"# or: {basis_cmd}"
                    ),
                    source=f"{surface['doc']}:{line_no}",
                )
            )

        # Reverse direction: only for surfaces that CLAIM to enumerate the whole flag set.
        if surface.get("complete"):
            for flag in sorted(declared - set(documented)):
                report.add(
                    Check(
                        check_id=f"cli_surface/{surface['id']}/complete/{flag}",
                        axis="cli_surface",
                        claim=(
                            f"{surface['doc']} claims to list the FULL CLI of "
                            f"{surface['target']}"
                        ),
                        code_truth=f"{flag} is declared by argparse but absent from the doc",
                        status="missing",
                        basis=(
                            f"ast: add_argument(\"--…\") in {surface['target']} minus the flags "
                            f"listed in the '{surface['marker']}' block"
                        ),
                        source=surface["doc"],
                    )
                )

    # ── (a2) documented `agentic-dynamics <group> <verb>` resolves through the dispatcher ────
    # The ground truth is the REAL resolver (`agentic_dynamics.cli._resolve`), not a re-derived
    # copy of the command table. Re-implementing the longest-prefix walk here would let the two
    # drift apart — the exact bug class this scanner exists to catch.
    resolve = _load_cli_resolver()
    if resolve is None:
        report.errors["cli_surface/tree"] = (
            f"cannot load _resolve from {ROOT}/src/agentic_dynamics/cli.py — "
            "subcommand claims are unverifiable and are NOT scored clean"
        )
        return

    tree_line = re.compile(r"agentic-dynamics\s+([a-z-]+)\s+(\S.*)$")
    for doc_rel in DOCUMENTED_CLI_TREES:
        doc_path = ROOT / doc_rel
        if not doc_path.is_file():
            continue
        # FENCE GUARD (false-positive fix): only lines INSIDE a fenced code block are read as
        # command claims. mental-model.md:49 is prose — "**`agentic-dynamics surfaces sync`**
        # regenerates every derived surface from its sources" — and a fence-blind scan split that
        # sentence into the "verbs" derived/every/from/its/regenerates, reporting six phantom
        # subcommands. Documented CLI trees are always fenced; prose that merely mentions a
        # command is not a claim about the command surface, so the fence IS the claim boundary.
        in_fence = False
        for i, raw in enumerate(_read(doc_path).splitlines(), start=1):
            if raw.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if not in_fence:
                continue
            line = raw.strip().lstrip("├└│─ ")
            # Two documented shapes: the `agentic-dynamics <group> <verbs>` command list, and the
            # box-drawing tree whose rows are `<group>   <verbs>`.
            match = tree_line.search(line)
            if match:
                group, verbs_blob = match.group(1), match.group(2)
            else:
                bare = re.match(r"^([a-z-]+)\s{2,}([a-z].*)$", line)
                if not bare:
                    continue
                group, verbs_blob = bare.group(1), bare.group(2)

            verbs_blob = verbs_blob.split("#")[0].strip().strip("`")
            for verb in re.split(r"[|\s]+", verbs_blob):
                verb = verb.strip("[]`,.").strip()
                # Placeholders such as `<name>` are argument slots, not verbs.
                if not verb or verb.startswith("<") or not re.match(r"^[a-z][a-z0-9-]*$", verb):
                    continue
                argv = [group, verb]
                # `analyze lab <name>` dispatches to `lab_<name>.py`; probe with a real lab so
                # the check exercises the documented path instead of skipping it.
                if (group, verb) == ("analyze", "lab"):
                    argv = ["analyze", "lab", "grit"]
                script, _rest = resolve(argv)
                ok = bool(script) and (ROOT / "scripts" / script).exists()
                report.add(
                    Check(
                        check_id=f"cli_surface/tree/{doc_rel}/{group}-{verb}",
                        axis="cli_surface",
                        claim=f"{doc_rel} documents `agentic-dynamics {group} {verb}`",
                        code_truth=(
                            f"resolves to scripts/{script}"
                            if ok
                            else f"does NOT resolve (cli._resolve -> {script!r})"
                        ),
                        status="current" if ok else "stale",
                        basis=(
                            f"python -c \"from agentic_dynamics.cli import _resolve; "
                            f"print(_resolve({argv!r}))\""
                        ),
                        source=f"{doc_rel}:{i}",
                    )
                )


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Axis (b) — module inventory
# ─────────────────────────────────────────────────────────────────────────────────────────────

#: ARCHITECTURE.md §1's pinned module-count claim. Whitespace-normalised before matching because
#: the sentence wraps mid-claim in the source.
_PINNED_MODULE_CLAIM = re.compile(
    r"(\d+)\s+tracked Python modules at the pinned SHA `([0-9a-f]{7,40})`"
)

#: The plane table row shape in §1: ``| `core` | … |``.
_PLANE_ROW = re.compile(r"^\|\s*`([a-z]+)`\s*\|")


def _modules_at(ref: str) -> int | None:
    """Count tracked ``src/agentic_dynamics/**/*.py`` at ``ref``, reproducing the doc's basis.

    The doc states its basis as ``git ls-files 'src/agentic_dynamics/**/*.py' | wc -l``. Git's
    ``**/`` glob requires at least one intervening directory, so the two plane-root modules
    (``__init__.py``, ``cli.py``) are NOT counted by that command. This function reproduces that
    exact semantics at an arbitrary ref via ``ls-tree`` (``ls-files`` only reads the index, so it
    cannot answer "at SHA X") by dropping paths with fewer than four components.

    Returns ``None`` when the ref does not resolve — the caller reports that as ``missing``
    rather than as a count mismatch, because an unresolvable anchor is a different defect.
    """
    if not _git("rev-parse", "--verify", f"{ref}^{{commit}}").strip():
        return None
    listing = _git("ls-tree", "-r", "--name-only", ref, "--", "src/agentic_dynamics/")
    return sum(
        1
        for path in listing.splitlines()
        if path.endswith(".py") and len(path.split("/")) > 3
    )


def check_module_inventory(report: DriftReport) -> None:
    """Axis (b): ARCHITECTURE.md's plane count and pinned module count match the tree."""
    arch = ROOT / "ARCHITECTURE.md"
    if not arch.is_file():
        report.errors["module_inventory"] = "ARCHITECTURE.md not found"
        return
    text = _read(arch)

    # ── (b1) the pinned module count, verified AT ITS PIN ────────────────────────────────────
    match = _PINNED_MODULE_CLAIM.search(_norm_ws(text))
    if not match:
        report.errors["module_inventory/pinned_count"] = (
            "ARCHITECTURE.md no longer carries a '<N> tracked Python modules at the pinned SHA "
            "`<sha>`' claim — the anchored-count convention was dropped or reworded"
        )
    else:
        claimed, sha = int(match.group(1)), match.group(2)
        actual = _modules_at(sha)
        if actual is None:
            status, truth = "missing", f"pinned SHA {sha} does not resolve in this repository"
        elif actual == claimed:
            status, truth = "current", f"{actual} modules at {sha[:12]}"
        else:
            status, truth = "stale", f"{actual} modules at {sha[:12]}, doc claims {claimed}"
        report.add(
            Check(
                check_id="module_inventory/pinned_module_count",
                axis="module_inventory",
                claim=f"ARCHITECTURE.md §1: {claimed} tracked Python modules at pinned SHA {sha[:12]}",
                code_truth=truth,
                status=status,
                basis=(
                    f"git ls-tree -r --name-only {sha} -- src/agentic_dynamics/ "
                    f"| grep '\\.py$' | awk -F/ 'NF>3' | wc -l"
                ),
                source="ARCHITECTURE.md",
            )
        )

    # ── (b2) the plane table matches the directories on disk ─────────────────────────────────
    documented_planes = {
        m.group(1)
        for m in (_PLANE_ROW.match(line) for line in text.splitlines())
        if m
    }
    # Restrict to rows that name a real or claimed plane (the table also carries a header rule).
    pkg = ROOT / "src" / "agentic_dynamics"
    actual_planes = {
        d.name for d in pkg.iterdir() if d.is_dir() and (d / "__init__.py").is_file()
    } if pkg.is_dir() else set()
    # Forward: every plane the §1 table names must exist as a package directory.
    for plane in sorted(documented_planes):
        exists = plane in actual_planes
        report.add(
            Check(
                check_id=f"module_inventory/plane/{plane}",
                axis="module_inventory",
                claim=f"ARCHITECTURE.md §1 documents plane `{plane}`",
                code_truth=(
                    f"src/agentic_dynamics/{plane}/ exists"
                    if exists
                    else f"src/agentic_dynamics/{plane}/ does not exist"
                ),
                status="current" if exists else "missing",
                basis=f"test -d src/agentic_dynamics/{plane}",
                source="ARCHITECTURE.md",
            )
        )

    # Every plane on disk must appear in the §1 table — a new plane that no doc names is exactly
    # the silent-drift class this axis exists for.
    for plane in sorted(actual_planes - documented_planes):
        report.add(
            Check(
                check_id=f"module_inventory/plane_undocumented/{plane}",
                axis="module_inventory",
                claim="ARCHITECTURE.md §1 enumerates the bounded planes",
                code_truth=f"src/agentic_dynamics/{plane}/ exists but §1 has no row for it",
                status="missing",
                basis="ls -d src/agentic_dynamics/*/ vs the §1 plane table rows",
                source="ARCHITECTURE.md",
            )
        )


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Axis (c) — spec lifecycle
# ─────────────────────────────────────────────────────────────────────────────────────────────

#: The "By the Numbers" spec figure: ``172 (11 experiments + 161 workflows)``.
_SPEC_COUNT_CLAIM = re.compile(r"(\d+)\s*\((\d+)\s*experiments?\s*\+\s*(\d+)\s*workflows?\)")


def _spec_index_counts() -> tuple[int, int] | None:
    """``(experiments, workflows)`` from the generated spec-lifecycle index, or None if absent."""
    index_path = ROOT / "experiments" / "specs" / "index.json"
    if not index_path.is_file():
        return None
    try:
        index = json.loads(_read(index_path))
    except json.JSONDecodeError:
        return None
    experiments = workflows = 0
    for spec in index.get("specs", []):
        kind = spec.get("artifact_kind")
        if kind == "experiment":
            experiments += 1
        elif kind == "workflow":
            workflows += 1
    return experiments, workflows


#: Documents that assert the repository's CURRENT inventory, and are therefore expected to track
#: it. Deliberately a whitelist, not a blacklist.
#:
#: A spec count is a time-stamped fact, so the axis is only meaningful where a doc claims to state
#: the count *now*. Most documents that mention a count are point-in-time records:
#: ``docs/reviews/cap_stabilization_release_adversary.md`` quotes "README reported 124 … while the
#: index held 125" as the very finding it filed, and ``HANDOFF.md`` records the count at handoff
#: time. Scanning those would flag a review for accurately quoting history and would pressure an
#: author to rewrite the record to match today's tree — drift-chasing that destroys evidence.
#: The current authorities below are the ones a reader treats as live.
CURRENT_INVENTORY_DOCS: tuple[str, ...] = (
    "README.md",
    "ARCHITECTURE.md",
    "agent_config/mental-model.md",
    "agent_config/rules.md",
    "agent_config/conventions.md",
)


def _source_markdown() -> list[Path]:
    """The current-authority documents whose inventory counts must track the tree."""
    return [
        ROOT / rel
        for rel in CURRENT_INVENTORY_DOCS
        if (ROOT / rel).is_file() and not _excluded(rel)
    ]


def check_spec_lifecycle(report: DriftReport) -> None:
    """Axis (c): documented spec counts match ``experiments/specs/index.json``."""
    counts = _spec_index_counts()
    if counts is None:
        report.errors["spec_lifecycle"] = (
            "experiments/specs/index.json missing or unparseable — spec counts unverifiable"
        )
        return
    n_exp, n_wf = counts
    total = n_exp + n_wf

    for path in _source_markdown():
        rel = path.relative_to(ROOT).as_posix()
        for i, line in enumerate(_read(path).splitlines(), start=1):
            match = _SPEC_COUNT_CLAIM.search(line)
            if not match:
                continue
            c_total, c_exp, c_wf = (int(g) for g in match.groups())
            ok = (c_total, c_exp, c_wf) == (total, n_exp, n_wf)
            report.add(
                Check(
                    check_id=f"spec_lifecycle/{rel}:{i}",
                    axis="spec_lifecycle",
                    claim=f"{rel}:{i} claims {c_total} specs ({c_exp} experiments + {c_wf} workflows)",
                    code_truth=f"index.json holds {total} ({n_exp} experiments + {n_wf} workflows)",
                    status="current" if ok else "stale",
                    basis=(
                        "python -c \"import json,collections;"
                        "print(collections.Counter(s['artifact_kind'] for s in "
                        "json.load(open('experiments/specs/index.json'))['specs']))\""
                    ),
                    source=f"{rel}:{i}",
                )
            )


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Axis (d) — status vocabulary
# ─────────────────────────────────────────────────────────────────────────────────────────────

#: The enforced lifecycle vocabulary. Mirrors ``tests/test_doc_lifecycle.py::STATUS_VOCABULARY``
#: exactly — the guard is the contract and the scanner must not invent a looser one.
STATUS_VOCABULARY = frozenset(
    {
        "proposed",
        "accepted",
        "implementing",
        "implemented",
        "superseded",
        "abandoned",
        "preregistered",
    }
)

#: Directory → required status, mirroring ``test_doc_lifecycle.py::test_kind_tree_statuses``.
#: The *kind* is carried by the directory, the *status* by the frontmatter.
KIND_TREE_STATUS: dict[str, str] = {
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


def check_status_vocabulary(report: DriftReport) -> None:
    """Axis (d): every source doc carries an enforced lifecycle status in its frontmatter."""
    # ── (d1) presence + vocabulary membership ────────────────────────────────────────────────
    # Root + docs/ only, matching the guard's own walk. agent_config/*.md are instruction sources
    # rendered into the agent surfaces, not lifecycle-managed documents, so the guard does not
    # require frontmatter on them and neither does this scanner.
    docs = sorted(ROOT.glob("*.md")) + sorted((ROOT / "docs").rglob("*.md"))
    for path in docs:
        rel = path.relative_to(ROOT).as_posix()
        if _excluded(rel):
            continue
        status = _front_matter(path).get("status")
        if status is None:
            state, truth = "missing", "no status field in frontmatter"
        elif status not in STATUS_VOCABULARY:
            state, truth = "stale", f"status={status!r} is outside the enforced vocabulary"
        else:
            state, truth = "current", f"status={status}"
        report.add(
            Check(
                check_id=f"status_vocabulary/frontmatter/{rel}",
                axis="status_vocabulary",
                claim=f"{rel} carries an enforced lifecycle status",
                code_truth=truth,
                status=state,
                basis=f"head -5 {rel}  # the leading --- frontmatter block",
                source=rel,
            )
        )

    # ── (d2) kind-tree agreement ─────────────────────────────────────────────────────────────
    for rel_dir, want in KIND_TREE_STATUS.items():
        tree = ROOT / rel_dir
        if not tree.is_dir():
            report.errors[f"status_vocabulary/{rel_dir}"] = "kind tree missing"
            continue
        for path in sorted(tree.glob("*.md")):
            rel = path.relative_to(ROOT).as_posix()
            got = _front_matter(path).get("status")
            ok = got == want
            report.add(
                Check(
                    check_id=f"status_vocabulary/kind_tree/{rel}",
                    axis="status_vocabulary",
                    claim=f"{rel_dir}/ entries are status: {want}",
                    code_truth=f"{rel} has status={got!r}",
                    status="current" if ok else "stale",
                    basis=f"head -5 {rel}",
                    source=rel,
                )
            )


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Axis (e) — anchor integrity
# ─────────────────────────────────────────────────────────────────────────────────────────────
#
# The `file:line` anchor is the docs' load-bearing provenance device, and it is the claim class
# that decays fastest: a refactor that moves code invalidates every anchor into it without
# touching a single doc.

#: A cited anchor: a backticked path with a line number, optionally a range (`:120-137`).
_ANCHOR = re.compile(
    r"`([A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:py|md|ts|tsx|yaml|yml|json|js|sh)):(\d+)(?:-(\d+))?`"
)

#: Base prefixes an anchor may be written relative to, in resolution order.
#:
#: Anchors in these docs are routinely written relative to an implicit base — `workflow_runner.py`
#: for the runtime plane, `app.js` for the portal's static dir. That is a documented house style,
#: not an error, so the resolver reproduces it with an EXPLICIT, ordered, reviewable list rather
#: than a permissive repo-wide basename search (which would resolve almost anything and gut the
#: check's power).
ANCHOR_BASES: tuple[str, ...] = (
    "",  # repo-relative — the strongest, tried first
    "src/agentic_dynamics/",
    "src/agentic_dynamics/core/",
    "src/agentic_dynamics/experiment/",
    "src/agentic_dynamics/measurement/",
    "src/agentic_dynamics/runtime/",
    "src/agentic_dynamics/adapters/",
    "src/agentic_dynamics/knowledge/",
    "src/agentic_dynamics/control/",
    "src/agentic_dynamics/control/reducers/",
    "src/agentic_dynamics/reporting/",
    "apps/control_room/",
    "apps/control_room/static/",
    "apps/control_room/routes/",
    "apps/website/",
    "docs/",
    "docs/architecture/current/",
    "docs/designs/proposed/",
    "docs/designs/implemented/",
    "docs/experiments/results/",
    "docs/release/consolidation/",
    "docs/reviews/",
    "docs/verification/",
    "docs/website/",
    "scripts/",
    "scripts/fleet/",
    "workflows/repository/",
    "experiments/specs/",
    "infrastructure/",
    "tests/",
)

#: Documented directory renames. An anchor written against a pre-rename path is not a *missing*
#: file — the reader can still find the code, and the rename is itself recorded in the repo's
#: history. Redirecting here upgrades the finding's accuracy: `admin/server.py:1365` becomes a
#: `stale` line finding against the real `apps/control_room/server.py` (which is now 214 lines,
#: so line 1365 is genuinely gone) instead of an imprecise `missing` path finding. Each entry is
#: falsifiable — the successor must exist, or the map itself is drift.
RETIRED_PATH_MAP: tuple[tuple[str, str], ...] = (
    ("admin/", "apps/control_room/"),                    # portal rename (Stage 5)
    ("code_reviews/", "docs/architecture/current/"),     # docs-taxonomy restructure
    ("experiments/specs/", "workflows/repository/"),     # rec-3 spec/work-order split
)


#: Cache for the tracked-file basename index. The scan resolves ~540 anchors; without this the
#: fallback would fork `git ls-files` once per unresolved anchor.
_BASENAME_INDEX: dict[str, list[str]] | None = None


#: Trees excluded from the anchor basename fallback. These hold agent-GENERATED payloads (story
#: worktree outputs, captured artifacts), not repository source, and they are full of ordinary
#: names — `server.py`, `app.py`, `main.py`. Without this exclusion a dangling anchor could be
#: silently "resolved" against an unrelated experiment artifact that happens to be long enough:
#: `admin/server.py:1365` sits beside seven captured `server.py` files under
#: experiments/results/artifacts/, and a longer one would have masked a real finding. This is a
#: false-NEGATIVE guard — the direction that makes a scanner useless rather than annoying.
BASENAME_FALLBACK_EXCLUDED = (
    "experiments/results/",
    "worktrees/",
    "node_modules/",
)


def _tracked_by_basename() -> dict[str, list[str]]:
    """Basename → tracked repo-relative SOURCE paths, built once per process."""
    global _BASENAME_INDEX
    if _BASENAME_INDEX is None:
        index: dict[str, list[str]] = defaultdict(list)
        for tracked in _git("ls-files").split():
            if tracked.startswith(BASENAME_FALLBACK_EXCLUDED):
                continue
            index[tracked.rsplit("/", 1)[-1]].append(tracked)
        _BASENAME_INDEX = dict(index)
    return _BASENAME_INDEX


def _anchor_candidates(path: str) -> list[Path]:
    """Every file the anchor path could denote, most-specific first.

    An anchor is judged ``current`` if ANY candidate has the cited line. Tolerating ambiguity is
    deliberate: several bare names (``spec_status.py`` exists three times) would otherwise be
    resolved to an arbitrary first match and reported as stale against the wrong file — a false
    positive, the failure mode the spec warns costs the most trust.
    """
    seen: list[Path] = []

    def _push(p: Path) -> None:
        if p.is_file() and p not in seen:
            seen.append(p)

    for base in ANCHOR_BASES:
        _push(ROOT / (base + path))
    # Documented renames, applied only when nothing resolved directly.
    if not seen:
        for old, new in RETIRED_PATH_MAP:
            if path.startswith(old):
                for base in ("", *ANCHOR_BASES):
                    _push(ROOT / (base + new + path[len(old):]))
    # Last resort: a basename index over TRACKED files only (never build artifacts or untracked
    # scratch). This is what separates "the file MOVED" from "the file is GONE", and it applies
    # to qualified paths too, not just bare names: `docs/supervisor_design.md:100-151` cites a
    # file that now lives at `docs/architecture/current/supervisor_design.md` (432 lines, so the
    # cited line is present and the claim still holds). Reporting that as `missing` was simply
    # imprecise. With this fallback, `missing` earns a sharp meaning — NO file of that name
    # exists anywhere in the tree — and `stale` means the file is findable but the cited line is
    # not, which is the anchor breakage a reader actually hits.
    if not seen:
        for tracked in _tracked_by_basename().get(path.rsplit("/", 1)[-1], ()):
            _push(ROOT / tracked)
    return seen


#: Documents whose anchors are in scope, per the spec: ARCHITECTURE.md + docs/architecture/current/.
def _anchor_scope() -> list[Path]:
    files = []
    arch = ROOT / "ARCHITECTURE.md"
    if arch.is_file():
        files.append(arch)
    current = ROOT / "docs" / "architecture" / "current"
    if current.is_dir():
        files += sorted(current.glob("*.md"))
    return files


def check_anchor_integrity(report: DriftReport) -> None:
    """Axis (e): every cited ``file:line`` anchor resolves to a file that has that line."""
    scope = _anchor_scope()
    if not scope:
        report.errors["anchor_integrity"] = "no documents in anchor scope"
        return

    for doc in scope:
        doc_rel = doc.relative_to(ROOT).as_posix()
        for i, line in enumerate(_read(doc).splitlines(), start=1):
            for match in _ANCHOR.finditer(line):
                cited_path, start_s, end_s = match.group(1), match.group(2), match.group(3)
                # For a range (`:120-137`) the END line is the binding constraint: if the file
                # reaches the last cited line it necessarily reaches the first.
                cited_line = int(end_s or start_s)
                candidates = _anchor_candidates(cited_path)
                anchor_text = f"{cited_path}:{start_s}" + (f"-{end_s}" if end_s else "")

                if not candidates:
                    status = "missing"
                    truth = f"no file named {cited_path} exists under any declared base"
                elif any(_line_count(c) >= cited_line for c in candidates):
                    status = "current"
                    hit = next(c for c in candidates if _line_count(c) >= cited_line)
                    truth = f"resolves to {hit.relative_to(ROOT).as_posix()} ({_line_count(hit)} lines)"
                else:
                    status = "stale"
                    detail = ", ".join(
                        f"{c.relative_to(ROOT).as_posix()}={_line_count(c)} lines"
                        for c in candidates[:3]
                    )
                    truth = f"line {cited_line} is past EOF in every candidate ({detail})"

                report.add(
                    Check(
                        check_id=f"anchor_integrity/{doc_rel}:{i}/{anchor_text}",
                        axis="anchor_integrity",
                        claim=f"{doc_rel}:{i} cites `{anchor_text}`",
                        code_truth=truth,
                        status=status,
                        basis=f"wc -l {cited_path}  # must be >= {cited_line}",
                        source=f"{doc_rel}:{i}",
                    )
                )


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Axis (f) — scripts/CONTEXT.md manifest
# ─────────────────────────────────────────────────────────────────────────────────────────────

_MANIFEST_START = "<!-- scripts-classification: start -->"
_MANIFEST_END = "<!-- scripts-classification: end -->"

#: Manifest buckets, mirroring ``tests/test_script_classification.py::BUCKETS``.
MANIFEST_BUCKETS = ("maintained", "historical", "one-time", "fleet")

#: Underscore-prefixed shared infrastructure, not commands — excluded by the guard, so excluded
#: here too (the scanner must agree with the guard exactly).
MANIFEST_HELPERS = {"_bootstrap.py", "_gen_instructions.py"}


def _parse_manifest() -> dict[str, set[str]]:
    """Parse the classification manifest from ``scripts/CONTEXT.md``.

    Note the union semantics: the manifest carries SEVERAL ``maintained:`` lines (the residue of
    union-resolved merge conflicts across parallel branches). The guard unions them and so does
    this parser — a script classified on any line is classified.
    """
    context = ROOT / "scripts" / "CONTEXT.md"
    text = _read(context)
    if _MANIFEST_START not in text or _MANIFEST_END not in text:
        raise ValueError("scripts/CONTEXT.md is missing the classification markers")
    body = text.split(_MANIFEST_START, 1)[1].split(_MANIFEST_END, 1)[0]
    manifest: dict[str, set[str]] = {b: set() for b in MANIFEST_BUCKETS}
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-")):
            continue
        for bucket in MANIFEST_BUCKETS:
            if line.startswith(bucket + ":"):
                manifest[bucket] |= set(line[len(bucket) + 1:].split())
    return manifest


def check_manifest_counts(report: DriftReport) -> None:
    """Axis (f): the CONTEXT.md manifest covers ``scripts/`` with no orphans and no phantoms."""
    scripts_dir = ROOT / "scripts"
    if not scripts_dir.is_dir():
        report.errors["manifest_counts"] = "scripts/ not found"
        return
    try:
        manifest = _parse_manifest()
    except (ValueError, OSError) as exc:
        report.errors["manifest_counts"] = str(exc)
        return

    on_disk = {p.name for p in scripts_dir.rglob("*.py")} - MANIFEST_HELPERS
    classified: set[str] = set().union(*manifest.values()) if manifest else set()

    # Orphans: a script exists but no bucket claims it — the manifest under-reports the surface.
    for name in sorted(on_disk - classified):
        report.add(
            Check(
                check_id=f"manifest_counts/orphan/{name}",
                axis="manifest_counts",
                claim="scripts/CONTEXT.md classifies every script in exactly one bucket",
                code_truth=f"scripts/**/{name} exists on disk but is in no manifest bucket",
                status="missing",
                basis="ls scripts/**/*.py vs the scripts-classification manifest block",
                source="scripts/CONTEXT.md",
            )
        )

    # Phantoms: a bucket names a script that is gone — the manifest over-reports the surface.
    for name in sorted(classified - on_disk):
        report.add(
            Check(
                check_id=f"manifest_counts/phantom/{name}",
                axis="manifest_counts",
                claim=f"scripts/CONTEXT.md classifies `{name}`",
                code_truth=f"{name} is not present under scripts/",
                status="stale",
                basis=f"find scripts -name {name}",
                source="scripts/CONTEXT.md",
            )
        )

    # Double-classification: a script in two buckets makes the "exactly one bucket" claim false.
    seen: dict[str, str] = {}
    for bucket in MANIFEST_BUCKETS:
        for name in sorted(manifest[bucket]):
            if name in seen:
                report.add(
                    Check(
                        check_id=f"manifest_counts/double/{name}",
                        axis="manifest_counts",
                        claim=f"`{name}` is in exactly one manifest bucket",
                        code_truth=f"{name} appears in both {seen[name]} and {bucket}",
                        status="stale",
                        basis="parse the scripts-classification block; intersect the buckets",
                        source="scripts/CONTEXT.md",
                    )
                )
            else:
                seen[name] = bucket

    # The positive row: the covered set. Without it a clean manifest would contribute no evidence
    # at all to the inventory, and "0 findings" could not be distinguished from "0 checks".
    report.add(
        Check(
            check_id="manifest_counts/coverage",
            axis="manifest_counts",
            claim="the manifest covers scripts/ exactly",
            code_truth=(
                f"{len(on_disk)} scripts on disk, {len(classified & on_disk)} classified, "
                f"{len(on_disk - classified)} orphans, {len(classified - on_disk)} phantoms"
            ),
            status="current" if on_disk == classified else "stale",
            basis="ls scripts/**/*.py vs the scripts-classification manifest block",
            source="scripts/CONTEXT.md",
        )
    )


# ─────────────────────────────────────────────────────────────────────────────────────────────


#: The fast-path command documented by ``scripts/CONTEXT.md`` (test_suite_speed p3-d wiring).
FAST_PATH_COMMAND = "scripts/test_fast.sh"
#: The gate module that enforces the fast-path budget (``FAST_BUDGET_SECONDS``).
FAST_PATH_GATE = "tests/test_fast_path_gate.py"
#: The ``scripts/CONTEXT.md`` budget phrasings the axis re-derives (``budget 180s …``).
_FAST_BUDGET_RE = re.compile(r"budget (\d+)s")
#: The gate constant the axis re-derives.
_FAST_BUDGET_CONSTANT_RE = re.compile(r"FAST_BUDGET_SECONDS\s*=\s*(\d+)")
#: The doc's fast-path section presence — the axis's source-doc precondition. When the doc no
#: longer documents the fast path at all, the axis CANNOT measure (it errors, unmeasurable)
#: rather than fabricate clean — the same contract as the manifest axis on a corrupted
#: ``scripts/CONTEXT.md``.
_FAST_PATH_DOC_RE = re.compile(r"test_fast\.sh|\bfast path\b|budget \d+s")


def check_fast_path(report: DriftReport) -> None:
    """Axis (g): the fast path that ``scripts/CONTEXT.md`` documents matches the code.

    The fast path (test_suite_speed p3) is the ``fast``-marked smoke the guards run on every
    change: ``scripts/CONTEXT.md`` documents the command (``scripts/test_fast.sh``) and the
    budget (the ``FAST_BUDGET_SECONDS`` trip wire, currently 180s). The gate enforces them in
    ``tests/test_fast_path_gate.py``. This axis re-derives both from the code and compares them
    against the doc — a doc that drifts from the gate, a gate whose budget/command the doc no
    longer names, or a marker set that silently empties, is caught by the same rail that scans
    every other current-authority claim.
    """
    context = ROOT / "scripts" / "CONTEXT.md"
    if not context.is_file():
        report.errors["fast_path"] = "scripts/CONTEXT.md not found"
        return
    context_text = context.read_text(encoding="utf-8")
    # The source doc is the fast-path section of scripts/CONTEXT.md. If the doc no longer
    # documents the fast path at all, the axis cannot measure — it errors (unmeasurable,
    # never scored clean) instead of reporting a fabricated clean.
    if not _FAST_PATH_DOC_RE.search(context_text):
        report.errors["fast_path"] = "scripts/CONTEXT.md does not document the fast path"
        return

    # ── (g1) the fast-path command ──────────────────────────────────────────
    command = ROOT / FAST_PATH_COMMAND
    command_text = command.read_text(encoding="utf-8") if command.is_file() else ""
    runs_marked_subset = bool(re.search(r"\bm\s+fast\b", command_text))
    if not command_text:
        report.add(
            Check(
                check_id="fast_path/command",
                axis="fast_path",
                claim="scripts/CONTEXT.md documents `bash scripts/test_fast.sh` as the fast-path command",
                code_truth=f"{FAST_PATH_COMMAND} does not exist",
                status="missing",
                basis="test -f scripts/test_fast.sh",
                source="scripts/CONTEXT.md",
            )
        )
    elif not runs_marked_subset:
        report.add(
            Check(
                check_id="fast_path/command",
                axis="fast_path",
                claim="scripts/CONTEXT.md documents `bash scripts/test_fast.sh` as the fast-path command",
                code_truth=f"{FAST_PATH_COMMAND} exists but does not invoke `pytest … -m fast`",
                status="stale",
                basis="grep -- '-m fast' scripts/test_fast.sh",
                source="scripts/CONTEXT.md",
            )
        )
    else:
        report.add(
            Check(
                check_id="fast_path/command",
                axis="fast_path",
                claim="scripts/CONTEXT.md documents `bash scripts/test_fast.sh` as the fast-path command",
                code_truth=f"{FAST_PATH_COMMAND} runs `pytest tests/ -m fast`",
                status="current",
                basis="grep -- '-m fast' scripts/test_fast.sh",
                source="scripts/CONTEXT.md",
            )
        )

    # ── (g2) the fast-path budget ──────────────────────────────────────────
    gate = ROOT / FAST_PATH_GATE
    gate_text = gate.read_text(encoding="utf-8") if gate.is_file() else ""
    const = _FAST_BUDGET_CONSTANT_RE.search(gate_text)
    doc = _FAST_BUDGET_RE.search(context_text)
    if const is None:
        report.add(
            Check(
                check_id="fast_path/budget",
                axis="fast_path",
                claim="scripts/CONTEXT.md documents the fast-path budget (180s) as a gate trip wire",
                code_truth=f"FAST_BUDGET_SECONDS is not defined in {FAST_PATH_GATE}",
                status="missing",
                basis=f"grep FAST_BUDGET_SECONDS {FAST_PATH_GATE}",
                source="scripts/CONTEXT.md",
            )
        )
    elif doc is None:
        report.add(
            Check(
                check_id="fast_path/budget",
                axis="fast_path",
                claim="scripts/CONTEXT.md documents the fast-path budget in seconds",
                code_truth=f"scripts/CONTEXT.md does not state a `budget Ns`; the gate enforces {const.group(1)}s",
                status="missing",
                basis="grep -E 'budget [0-9]+s' scripts/CONTEXT.md",
                source="scripts/CONTEXT.md",
            )
        )
    elif int(const.group(1)) != int(doc.group(1)):
        report.add(
            Check(
                check_id="fast_path/budget",
                axis="fast_path",
                claim=f"scripts/CONTEXT.md documents the fast-path budget as {doc.group(1)}s",
                code_truth=f"the gate's FAST_BUDGET_SECONDS is {const.group(1)}s — the doc and the gate disagree",
                status="stale",
                basis=f"grep FAST_BUDGET_SECONDS {FAST_PATH_GATE} vs grep -E 'budget [0-9]+s' scripts/CONTEXT.md",
                source="scripts/CONTEXT.md",
            )
        )
    else:
        report.add(
            Check(
                check_id="fast_path/budget",
                axis="fast_path",
                claim=f"scripts/CONTEXT.md documents the fast-path budget as {doc.group(1)}s",
                code_truth=f"the gate's FAST_BUDGET_SECONDS is {const.group(1)}s — the doc and the gate agree",
                status="current",
                basis=f"grep FAST_BUDGET_SECONDS {FAST_PATH_GATE} vs grep -E 'budget [0-9]+s' scripts/CONTEXT.md",
                source="scripts/CONTEXT.md",
            )
        )

    # ── (g3) the fast-path subset is non-empty ──────────────────────────────────────────
    tests_dir = ROOT / "tests"
    marked = (
        sorted(
            p
            for p in tests_dir.glob("test_*.py")
            if re.search(r"^pytestmark\s*=\s*pytest\.mark\.fast\b", p.read_text(), re.M)
        )
        if tests_dir.is_dir()
        else []
    )
    if marked:
        report.add(
            Check(
                check_id="fast_path/subset",
                axis="fast_path",
                claim="scripts/CONTEXT.md documents the fast subset as the audited `fast`-marked families",
                code_truth=f"{len(marked)} test modules carry `pytestmark = pytest.mark.fast`",
                status="current",
                basis="grep -l 'pytest.mark.fast' tests/test_*.py",
                source="scripts/CONTEXT.md",
            )
        )
    else:
        report.add(
            Check(
                check_id="fast_path/subset",
                axis="fast_path",
                claim="scripts/CONTEXT.md documents the fast subset as the audited `fast`-marked families",
                code_truth="no test module carries `pytestmark = pytest.mark.fast` — the fast path is empty",
                status="stale",
                basis="grep -l 'pytest.mark.fast' tests/test_*.py",
                source="scripts/CONTEXT.md",
            )
        )


# Orchestration
# ─────────────────────────────────────────────────────────────────────────────────────────────

#: Axis id → check function. The single registry the CLI, the tests, and the report all read.
CHECKS = {
    "cli_surface": check_cli_surface,
    "module_inventory": check_module_inventory,
    "spec_lifecycle": check_spec_lifecycle,
    "status_vocabulary": check_status_vocabulary,
    "anchor_integrity": check_anchor_integrity,
    "manifest_counts": check_manifest_counts,
    "fast_path": check_fast_path,
}


def scan(axes: tuple[str, ...] = AXES) -> DriftReport:
    """Run the requested axes and return the assembled report.

    A check that raises is recorded in ``report.errors`` rather than aborting the scan: a broken
    axis must not hide the findings of the other axes, and an errored axis is reported as
    unmeasured rather than scored clean.
    """
    report = DriftReport()
    for axis in axes:
        try:
            CHECKS[axis](report)
        except Exception as exc:  # pragma: no cover - defensive; keeps one axis from killing all
            report.errors[axis] = f"{type(exc).__name__}: {exc}"
    return report


def _render_summary(report: DriftReport) -> str:
    """Human-readable summary — the check inventory, the per-axis score, and the findings."""
    score = report.score()
    lines = [
        "docs-drift scan (deterministic, zero model calls)",
        f"  repo HEAD: {_git_head()[:12]}",
        "",
        f"  {'axis':<20} {'checked':>8} {'current':>8} {'stale':>7} {'missing':>8} {'drift':>7}",
        f"  {'-' * 20} {'-' * 8} {'-' * 8} {'-' * 7} {'-' * 8} {'-' * 7}",
    ]
    for axis in AXES:
        b = score["per_axis"].get(axis)
        if not b:
            continue
        lines.append(
            f"  {axis:<20} {b['checked']:>8} {b['current']:>8} {b['stale']:>7} "
            f"{b['missing']:>8} {b['drift']:>7}"
        )
    lines += [
        f"  {'-' * 20} {'-' * 8} {'-' * 8} {'-' * 7} {'-' * 8} {'-' * 7}",
        f"  {'TOTAL':<20} {score['total_checked']:>8} {score['total_current']:>8} "
        f"{score['total_stale']:>7} {score['total_missing']:>8} {score['drift']:>7}",
        "",
        f"  DRIFT SCORE: {score['drift']}",
    ]
    if report.errors:
        lines += ["", "  UNMEASURED AXES (errored — not scored clean):"]
        lines += [f"    {k}: {v}" for k, v in sorted(report.errors.items())]
    if report.findings:
        lines += ["", "  findings:"]
        by_axis: dict[str, list[Check]] = defaultdict(list)
        for finding in report.findings:
            by_axis[finding.axis].append(finding)
        for axis in AXES:
            if axis not in by_axis:
                continue
            lines.append(f"    [{axis}]")
            for finding in by_axis[axis]:
                lines.append(f"      {finding.status.upper():<8} {finding.source}")
                lines.append(f"               claim: {finding.claim}")
                lines.append(f"               code:  {finding.code_truth}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. See the module docstring for usage and exit codes."""
    parser = argparse.ArgumentParser(
        description="Deterministic docs-drift scanner (zero model calls).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--json",
        metavar="PATH",
        help="write the machine-readable JSON drift report to PATH ('-' for stdout)",
    )
    parser.add_argument(
        "--check",
        action="append",
        choices=AXES,
        help="run only this axis (repeatable); default: all seven",
    )
    parser.add_argument(
        "--include-current",
        action="store_true",
        help="serialize every check row, not just the findings (the full inventory)",
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="exit 1 when the drift score is non-zero (for the watchdog / CI)",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress the human summary")
    args = parser.parse_args(argv)

    axes = tuple(args.check) if args.check else AXES
    report = scan(axes)

    if args.json:
        payload = json.dumps(report.to_json(include_current=args.include_current), indent=2)
        if args.json == "-":
            print(payload)
        else:
            out = Path(args.json)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(payload + "\n", encoding="utf-8")

    if not args.quiet:
        print(_render_summary(report), file=sys.stderr if args.json == "-" else sys.stdout)

    # An axis that could not run is a SCAN failure, not a clean result — and it is loud
    # regardless of --fail-on-drift. A partial scan reporting "drift 0" is the most dangerous
    # output this tool can produce: it reads exactly like a clean tree. Exit 2 keeps "I could not
    # measure" distinguishable from both "clean" (0) and "drift found" (1).
    if report.errors:
        return 2
    if args.fail_on_drift and report.score()["drift"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
