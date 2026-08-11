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
    """Compute AST-level diff between two commits.

    Checks out each commit in turn, parses the codebase with tree-sitter,
    and compares structural counts.

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
    lines_stat = _run_git(worktree, "diff", "--numstat", f"{parent_commit}..{child_commit}")

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

    # Count files changed
    files_changed = _run_git(
        worktree, "diff", "--name-status", f"{parent_commit}..{child_commit}"
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

    # Parse codebase at each commit using temporary checkouts
    before_ast = _parse_at_commit(worktree, parent_commit, profile)
    after_ast = _parse_at_commit(worktree, child_commit, profile)

    funcs_delta = 0
    classes_delta = 0
    imports_delta = 0

    if before_ast and after_ast:
        funcs_delta = after_ast.function_count - before_ast.function_count
        classes_delta = after_ast.class_count - before_ast.class_count
        imports_delta = after_ast.import_count - before_ast.import_count

    return CommitAnalysis(
        commit_hash=child_commit,
        commit_message=msg,
        files_added=files_added,
        files_modified=files_modified,
        files_deleted=files_deleted,
        functions_added=max(funcs_delta, 0),
        functions_removed=abs(min(funcs_delta, 0)),
        classes_added=max(classes_delta, 0),
        classes_removed=abs(min(classes_delta, 0)),
        imports_added=max(imports_delta, 0),
        imports_removed=abs(min(imports_delta, 0)),
        lines_added=lines_added,
        lines_removed=lines_removed,
    )


def _parse_at_commit(
    worktree: Path, commit: str, profile: LanguageProfile | None
) -> CodebaseAST | None:
    """Parse the codebase at a specific commit using a temporary worktree."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "checkout"
        _run_git(worktree, "worktree", "add", "--detach", str(tmp_path), commit)
        try:
            return parse_codebase(tmp_path, profile)
        finally:
            _run_git(worktree, "worktree", "remove", "--force", str(tmp_path))


# ── Convention Scoring ─────────────────────────────────────────

def score_conventions(
    worktree: Path,
    commit: str,
    profile: LanguageProfile | None = None,
) -> tuple[float, list[str]]:
    """Score how well the codebase at a commit follows language conventions.

    Returns:
        (score 0.0-1.0, list of violation descriptions)
    """
    if profile is None:
        profile = detect_language(worktree)
    if profile is None:
        return 1.0, []

    rules = get_convention_rules(profile.name)
    violations: list[str] = []
    checks_passed = 0
    checks_total = 0

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "checkout"
        _run_git(worktree, "worktree", "add", "--detach", str(tmp_path), commit)
        try:
            for ext in profile.extensions:
                for fp in tmp_path.rglob(f"*{ext}"):
                    if any(skip in str(fp) for skip in ["__pycache__", "node_modules", ".git"]):
                        continue
                    try:
                        content = fp.read_text()
                    except (OSError, UnicodeDecodeError):
                        continue

                    # Check naming patterns
                    for pattern in rules.naming_patterns:
                        checks_total += 1
                        if re.search(pattern, content):
                            checks_passed += 1
                        else:
                            violations.append(
                                f"{fp.name}: no match for naming pattern {pattern}"
                            )

        finally:
            _run_git(worktree, "worktree", "remove", "--force", str(tmp_path))

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
    """Run all analysis layers on a single commit.

    Convenience function that runs AST diff, convention scoring,
    and SonarQube delta in one call.

    Args:
        worktree: Git worktree path.
        parent_commit: Parent commit hash.
        child_commit: Child commit hash.
        session_number: Session number for labeling.

    Returns:
        Fully populated CommitAnalysis.
    """
    analysis = compute_ast_diff(worktree, parent_commit, child_commit)
    analysis.session_number = session_number

    # Convention score
    score, violations = score_conventions(worktree, child_commit)
    analysis.convention_score = score
    analysis.convention_violations = violations

    # SonarQube delta
    sonar = compute_sonar_delta(worktree, parent_commit, child_commit)
    analysis.sonar_available = sonar["available"]
    analysis.sonar_bugs_delta = sonar["bugs_delta"]
    analysis.sonar_smells_delta = sonar["smells_delta"]
    analysis.sonar_complexity_delta = sonar["complexity_delta"]
    analysis.sonar_duplications_delta = sonar["duplications_delta"]

    return analysis


def analyze_story_worktree(worktree: Path) -> StoryAnalysis:
    """Analyze all commits in a story worktree.

    Walks the git log, finds consecutive commit pairs, and runs
    the full analysis pipeline on each.

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

    # Analyze each pair (skip seed + mutation commits, focus on session commits)
    session_num = 0
    for i in range(1, len(commits)):
        parent_hash, _ = commits[i - 1]
        child_hash, child_msg = commits[i]

        # Only analyze session commits (those from our instrument)
        if "[story]" in child_msg or "Session" in child_msg:
            session_num += 1
            analysis = analyze_commit(worktree, parent_hash, child_hash, session_num)
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
