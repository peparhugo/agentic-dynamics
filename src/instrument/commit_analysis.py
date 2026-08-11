"""Per-commit analysis — AST diff, SonarQube delta, convention scoring.

Analyzes each commit in a story to measure what the agent changed
and whether those changes improved or degraded the codebase.

Layers:
  1. AST diff — file/function/class/import counts via tree-sitter
  2. SonarQube delta — bugs, smells, complexity drift
  3. Convention adherence — pattern consistency with seed codebase
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .language import detect_language, parse_codebase, LanguageProfile, CodebaseAST


# ── Data Structures ────────────────────────────────────────────

@dataclass
class ConventionRules:
    """Per-language convention checks."""

    language: str
    naming_patterns: list[str] = field(default_factory=list)
    required_imports: list[str] = field(default_factory=list)
    forbidden_patterns: list[str] = field(default_factory=list)
    docstring_required: bool = False


@dataclass
class CommitAnalysis:
    """Per-commit analysis result."""

    commit_hash: str
    commit_message: str = ""
    session_number: int = 0

    # AST diff
    files_added: int = 0
    files_modified: int = 0
    files_deleted: int = 0
    functions_added: int = 0
    functions_removed: int = 0
    classes_added: int = 0
    classes_removed: int = 0
    imports_added: int = 0
    imports_removed: int = 0
    lines_added: int = 0
    lines_removed: int = 0

    # SonarQube delta (populated if SonarQube available)
    sonar_available: bool = False
    sonar_bugs_delta: int = 0
    sonar_smells_delta: int = 0
    sonar_complexity_delta: int = 0
    sonar_duplications_delta: float = 0.0

    # Convention
    convention_score: float = 0.0
    convention_violations: list[str] = field(default_factory=list)

    # Review (populated by review agent)
    review_score: float | None = None
    review_problems: list[str] = field(default_factory=list)
    review_better_or_worse: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "commit_hash": self.commit_hash,
            "commit_message": self.commit_message,
            "session_number": self.session_number,
            "ast": {
                "files_added": self.files_added,
                "files_modified": self.files_modified,
                "files_deleted": self.files_deleted,
                "functions_added": self.functions_added,
                "functions_removed": self.functions_removed,
                "classes_added": self.classes_added,
                "classes_removed": self.classes_removed,
                "imports_added": self.imports_added,
                "imports_removed": self.imports_removed,
                "lines_added": self.lines_added,
                "lines_removed": self.lines_removed,
            },
            "sonar": {
                "available": self.sonar_available,
                "bugs_delta": self.sonar_bugs_delta,
                "smells_delta": self.sonar_smells_delta,
                "complexity_delta": self.sonar_complexity_delta,
                "duplications_delta": self.sonar_duplications_delta,
            },
            "convention": {
                "score": self.convention_score,
                "violations": self.convention_violations,
            },
            "review": {
                "score": self.review_score,
                "problems": self.review_problems,
                "better_or_worse": self.review_better_or_worse,
            },
        }


@dataclass
class StoryAnalysis:
    """Aggregate analysis across all commits in a story."""

    story_name: str
    story_id: str = ""
    language: str = ""
    commits: list[CommitAnalysis] = field(default_factory=list)

    @property
    def total_lines_added(self) -> int:
        return sum(c.lines_added for c in self.commits)

    @property
    def total_lines_removed(self) -> int:
        return sum(c.lines_removed for c in self.commits)

    @property
    def net_lines(self) -> int:
        return self.total_lines_added - self.total_lines_removed

    @property
    def average_convention_score(self) -> float:
        if not self.commits:
            return 0.0
        return sum(c.convention_score for c in self.commits) / len(self.commits)

    def to_dict(self) -> dict[str, Any]:
        return {
            "story_name": self.story_name,
            "story_id": self.story_id,
            "language": self.language,
            "summary": {
                "commits": len(self.commits),
                "total_lines_added": self.total_lines_added,
                "total_lines_removed": self.total_lines_removed,
                "net_lines": self.net_lines,
                "average_convention_score": round(self.average_convention_score, 3),
            },
            "commits": [c.to_dict() for c in self.commits],
        }


# ── Convention Rules ───────────────────────────────────────────

PYTHON_CONVENTIONS = ConventionRules(
    language="python",
    naming_patterns=[
        r"def [a-z_][a-z0-9_]*\(",     # snake_case functions
        r"class [A-Z][a-zA-Z0-9]*\:",    # PascalCase classes
    ],
    required_imports=[],
    forbidden_patterns=[],
    docstring_required=False,
)

TYPESCRIPT_CONVENTIONS = ConventionRules(
    language="typescript",
    naming_patterns=[
        r"function [a-z][a-zA-Z0-9]*\(",  # camelCase functions
        r"class [A-Z][a-zA-Z0-9]*\{",      # PascalCase classes
    ],
    required_imports=[],
    forbidden_patterns=[],
    docstring_required=False,
)

_CONVENTIONS: dict[str, ConventionRules] = {
    "python": PYTHON_CONVENTIONS,
    "typescript": TYPESCRIPT_CONVENTIONS,
}


def get_convention_rules(language: str) -> ConventionRules:
    return _CONVENTIONS.get(language, ConventionRules(language=language))


# ── AST Diff ───────────────────────────────────────────────────

def compute_ast_diff(
    worktree: Path,
    parent_commit: str,
    child_commit: str,
    profile: LanguageProfile | None = None,
) -> CommitAnalysis:
    """Compute AST-level diff between two commits using git diff stats.

    Uses `git diff` (instant) instead of temporary worktrees.
    No git worktree creation — all metrics from the diff output.

    Args:
        worktree: Path to the git worktree.
        parent_commit: Parent commit hash (or "HEAD~1").
        child_commit: Child commit hash (or "HEAD").
        profile: Language profile. Auto-detected if None.

    Returns:
        CommitAnalysis with AST diff fields populated.
    """
    if profile is None:
        profile = detect_language(worktree)

    # Get commit metadata
    msg = _run_git(worktree, "log", "-1", "--format=%s", child_commit).strip()

    # Lines: git diff --numstat (instant)
    lines_stat = _run_git(
        worktree, "diff", "--numstat",
        "--", ":", "!node_modules", ":", "!dist", ":", "!.instrument",
        f"{parent_commit}..{child_commit}"
    )
    lines_added = 0
    lines_removed = 0
    for line in lines_stat.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            try:
                lines_added += int(parts[0]) if parts[0] != "-" else 0
                lines_removed += int(parts[1]) if parts[1] != "-" else 0
            except ValueError:
                pass

    # Files: git diff --name-status (instant)
    files_changed = _run_git(
        worktree, "diff", "--name-status",
        "--", ":", "!node_modules", ":", "!dist", ":", "!.instrument",
        f"{parent_commit}..{child_commit}"
    )
    files_added = 0
    files_modified = 0
    files_deleted = 0
    for line in files_changed.splitlines():
        if line.startswith("A"):
            files_added += 1
        elif line.startswith("M"):
            files_modified += 1
        elif line.startswith("D"):
            files_deleted += 1

    # Functions/classes/imports: count + and - lines in the diff
    # For Python: +def , +class , +import , +from
    # For TypeScript: +function , +class , +import
    if profile.name == "python":
        func_pattern = r"\n\+def "
        async_func = r"\n\+async def "
        class_pattern = r"\n\+class "
        import_patterns = (r"\n\+import ", r"\n\+from ")
        func_rem_pattern = r"\n\-def "
        async_rem = r"\n\-async def "
        class_rem_pattern = r"\n\-class "
        import_rem_patterns = (r"\n\-import ", r"\n\-from ")
    else:
        func_pattern = r"\n\+function "
        async_func = r"\n\+async function "
        class_pattern = r"\n\+class "
        import_patterns = (r"\n\+import ",)
        func_rem_pattern = r"\n\-function "
        async_rem = r"\n\-async function "
        class_rem_pattern = r"\n\-class "
        import_rem_patterns = (r"\n\-import ",)

    import re
    diff_text = _run_git(
        worktree, "diff",
        "--", ":", "!node_modules", ":", "!dist", ":", "!.instrument",
        f"{parent_commit}..{child_commit}"
    )

    funcs_added = len(re.findall(func_pattern, diff_text)) + len(re.findall(async_func, diff_text))
    funcs_removed = len(re.findall(func_rem_pattern, diff_text)) + len(re.findall(async_rem, diff_text))
    classes_added = len(re.findall(class_pattern, diff_text))
    classes_removed = len(re.findall(class_rem_pattern, diff_text))

    imports_added = 0
    imports_removed = 0
    for pat in import_patterns:
        imports_added += len(re.findall(pat, diff_text))
    for pat in import_rem_patterns:
        imports_removed += len(re.findall(pat, diff_text))

    return CommitAnalysis(
        commit_hash=child_commit,
        commit_message=msg,
        files_added=files_added,
        files_modified=files_modified,
        files_deleted=files_deleted,
        functions_added=funcs_added,
        functions_removed=funcs_removed,
        classes_added=classes_added,
        classes_removed=classes_removed,
        imports_added=imports_added,
        imports_removed=imports_removed,
        lines_added=lines_added,
        lines_removed=lines_removed,
    )


def score_conventions(
    worktree: Path,
    commit: str | None = None,
    profile: LanguageProfile | None = None,
) -> tuple[float, list[str]]:
    """Score how well the current worktree follows language conventions.

    Uses ``git ls-files`` to avoid descending into node_modules.
    """
    if profile is None:
        profile = detect_language(worktree)
    if profile is None:
        return 1.0, []

    rules = get_convention_rules(profile.name)
    violations: list[str] = []
    checks_passed = 0
    checks_total = 0

    # Use git ls-files to get only tracked source files (avoids node_modules)
    tracked = _run_git(worktree, "ls-files", "--cached", "--others", "--exclude-standard")
    for rel_path in tracked.splitlines():
        rel_path = rel_path.strip()
        if not rel_path:
            continue
        fp = worktree / rel_path
        if fp.suffix not in profile.extensions:
            continue
        try:
            content = fp.read_text()
        except (OSError, UnicodeDecodeError):
            continue

        for pattern in rules.naming_patterns:
            checks_total += 1
            if re.search(pattern, content):
                checks_passed += 1
            else:
                violations.append(f"{fp.name}: no match for naming pattern {pattern}")

    if checks_total == 0:
        return 1.0, []

    score = checks_passed / checks_total
    return score, violations


# ── SonarQube Delta ────────────────────────────────────────────

def compute_sonar_delta(
    worktree: Path,
    parent_commit: str,
    child_commit: str,
    *,
    sonar_url: str = "http://127.0.0.1:9000",
    sonar_token: str = "",
) -> dict[str, Any]:
    """Compute SonarQube metric deltas between two commits.

    Checks if SonarQube is reachable, and if so, runs analysis at both
    commits and computes the delta.

    Returns dict with delta values. All zero if SonarQube unavailable.
    """
    try:
        from .sonar import run_sonar_analysis, SonarMetrics
    except ImportError:
        return _empty_sonar_delta()

    # Check if SonarQube is available
    try:
        import urllib.request
        urllib.request.urlopen(f"{sonar_url}/api/system/status", timeout=5)
    except Exception:
        return {"available": False, "bugs_delta": 0, "smells_delta": 0,
                "complexity_delta": 0, "duplications_delta": 0.0}

    # Run analysis at each commit
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        parent_path = tmp_path / "parent"
        child_path = tmp_path / "child"

        _run_git(worktree, "worktree", "add", "--detach", str(parent_path), parent_commit)
        _run_git(worktree, "worktree", "add", "--detach", str(child_path), child_commit)

        try:
            parent_sm = run_sonar_analysis(
                parent_path, sonar_url=sonar_url,
                sonar_user=sonar_token or "", sonar_password="",
            )
            child_sm = run_sonar_analysis(
                child_path, sonar_url=sonar_url,
                sonar_user=sonar_token or "", sonar_password="",
            )

            if parent_sm and child_sm and parent_sm.analyzed and child_sm.analyzed:
                return {
                    "available": True,
                    "bugs_delta": child_sm.bugs - parent_sm.bugs,
                    "smells_delta": child_sm.code_smells - parent_sm.code_smells,
                    "complexity_delta": child_sm.cognitive_complexity - parent_sm.cognitive_complexity,
                    "duplications_delta": child_sm.duplicated_lines_density - parent_sm.duplicated_lines_density,
                }
        finally:
            _run_git(worktree, "worktree", "remove", "--force", str(parent_path))
            _run_git(worktree, "worktree", "remove", "--force", str(child_path))

    return _empty_sonar_delta()


def _empty_sonar_delta() -> dict[str, Any]:
    return {
        "available": False,
        "bugs_delta": 0,
        "smells_delta": 0,
        "complexity_delta": 0,
        "duplications_delta": 0.0,
    }


# ── Full Commit Analysis ───────────────────────────────────────

def analyze_commit(
    worktree: Path,
    parent_commit: str,
    child_commit: str,
    session_number: int = 0,
) -> CommitAnalysis:
    """Run all analysis layers on a single commit."""
    analysis = compute_ast_diff(worktree, parent_commit, child_commit)
    analysis.session_number = session_number
    return analysis


def analyze_story_worktree(worktree: Path) -> StoryAnalysis:
    """Analyze all commits in a story worktree.

    Walks the git log, finds consecutive commit pairs, and runs
    the full analysis pipeline on each. Convention scoring is done
    once at the story level (current worktree state).

    Args:
        worktree: Path to the story worktree with git history.

    Returns:
        StoryAnalysis with per-commit results.
    """
    # Get all commit hashes in chronological order (oldest first)
    log = _run_git(worktree, "log", "--reverse", "--format=%H %s")
    commits = []
    for line in log.splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2:
            commits.append((parts[0], parts[1]))

    if len(commits) < 2:
        return StoryAnalysis(story_name="unknown")

    language = ""
    profile = detect_language(worktree)
    if profile:
        language = profile.name

    story = StoryAnalysis(story_name="unknown", language=language)

    # Score conventions once on the final state (not per commit)
    final_score, final_violations = score_conventions(worktree, profile=profile)

    # Analyze each pair (skip seed + mutation commits, focus on session commits)
    session_num = 0
    for i in range(1, len(commits)):
        parent_hash, _ = commits[i - 1]
        child_hash, child_msg = commits[i]

        # Only analyze session commits (those from our instrument)
        if "[story]" in child_msg or "Session" in child_msg:
            session_num += 1
            analysis = analyze_commit(worktree, parent_hash, child_hash, session_num)
            analysis.convention_score = final_score
            analysis.convention_violations = final_violations
            story.commits.append(analysis)

    return story


# ── Git Helpers ────────────────────────────────────────────────

def _run_git(worktree: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git"] + list(args),
            capture_output=True,
            text=True,
            cwd=str(worktree),
            timeout=60,
        )
        return proc.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""
