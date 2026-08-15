"""Per-commit analysis — AST diff, SonarQube delta, convention scoring.

Analyzes each commit in a story to measure what the agent changed
and whether those changes improved or degraded the codebase.

Layers:
  1. AST diff — file/function/class/import counts via tree-sitter
  2. SonarQube delta — bugs, smells, complexity drift
  3. Convention adherence — pattern consistency with seed codebase
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .language import LanguageProfile, detect_language

# ── Data Structures ────────────────────────────────────────────

@dataclass
class ConventionRule:
    """A single naming or forbidden pattern rule."""

    name: str
    description: str = ""
    pattern: str = ""


@dataclass
class ConventionRules:
    """Per-language convention checks loaded from YAML."""

    language: str
    naming_patterns: list[ConventionRule] = field(default_factory=list)
    forbidden_patterns: list[ConventionRule] = field(default_factory=list)
    scoring: dict[str, float] = field(default_factory=dict)


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

_CONVENTIONS_CACHE: dict[str, ConventionRules] = {}
_CONVENTIONS_DIR = Path(__file__).resolve().parent.parent.parent / "conventions"


def _load_yaml_conventions(language: str) -> ConventionRules | None:
    """Load convention rules from a YAML file."""
    yaml_path = _CONVENTIONS_DIR / f"{language}.yaml"
    if not yaml_path.exists():
        return None
    try:
        data = yaml.safe_load(yaml_path.read_text())
    except (yaml.YAMLError, OSError):
        return None

    naming = [
        ConventionRule(name=r["name"], description=r["description"], pattern=r["pattern"])
        for r in data.get("naming_patterns", [])
    ]

    forbidden = [
        ConventionRule(name=r["name"], description=r["description"], pattern=r["pattern"])
        for r in data.get("forbidden_patterns", [])
    ]

    scoring = data.get("scoring", {})

    return ConventionRules(
        language=data.get("language", language),
        naming_patterns=naming,
        forbidden_patterns=forbidden,
        scoring=scoring,
    )


def get_convention_rules(language: str) -> ConventionRules:
    """Get convention rules for a language, loaded from YAML conventions file."""
    if language not in _CONVENTIONS_CACHE:
        rules = _load_yaml_conventions(language)
        if rules is None:
            rules = ConventionRules(language=language)
        _CONVENTIONS_CACHE[language] = rules
    return _CONVENTIONS_CACHE[language]


# ── AST Diff ───────────────────────────────────────────────────

def compute_ast_diff(
    worktree: Path,
    parent_commit: str,
    child_commit: str,
    profile: LanguageProfile | None = None,
) -> CommitAnalysis:
    """Compute diff-level structural changes between two commits.

    Uses `git diff` (instant) instead of temporary worktrees. The structural
    counts (functions/classes/imports) are a regex diff-stat *heuristic*, not a
    tree-sitter AST — kept under this name for API compatibility. Language-aware
    patterns cover Python, TypeScript, Go, and Rust.

    Args:
        worktree: Path to the git worktree.
        parent_commit: Parent commit hash (or "HEAD~1").
        child_commit: Child commit hash (or "HEAD").
        profile: Language profile. Auto-detected if None.

    Returns:
        CommitAnalysis with diff fields populated.
    """
    if profile is None:
        profile = detect_language(worktree)

    # Get commit metadata
    msg = _run_git(worktree, "log", "-1", "--format=%s", child_commit).strip()

    # Lines: git diff --numstat (instant)
    lines_stat = _run_git(
        worktree, "diff", "--numstat",
        f"{parent_commit}..{child_commit}",
        "--", ":(exclude)node_modules", ":(exclude)dist", ":(exclude).instrument", ":(exclude)__pycache__", ":(exclude).pytest_cache",
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
        f"{parent_commit}..{child_commit}",
        "--", ":(exclude)node_modules", ":(exclude)dist", ":(exclude).instrument", ":(exclude)__pycache__", ":(exclude).pytest_cache",
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

    # Functions/classes/imports: count + and - lines in the diff.
    # This is a diff-stat *heuristic* (regex on git diff hunks), not a
    # tree-sitter AST — the function name is retained for API compatibility.
    # Patterns per language so Go/Rust are not miscounted as zero.
    if profile.name == "python":
        func_pattern = r"\n\+def "
        async_func = r"\n\+async def "
        class_pattern = r"\n\+class "
        import_patterns = (r"\n\+import ", r"\n\+from ")
        func_rem_pattern = r"\n\-def "
        async_rem = r"\n\-async def "
        class_rem_pattern = r"\n\-class "
        import_rem_patterns = (r"\n\-import ", r"\n\-from ")
    elif profile.name == "typescript":
        func_pattern = r"\n\+function "
        async_func = r"\n\+async function "
        class_pattern = r"\n\+class "
        import_patterns = (r"\n\+import ",)
        func_rem_pattern = r"\n\-function "
        async_rem = r"\n\-async function "
        class_rem_pattern = r"\n\-class "
        import_rem_patterns = (r"\n\-import ",)
    elif profile.name == "go":
        func_pattern = r"\n\+func "
        async_func = r"(?!)"  # Go has no async functions
        class_pattern = r"\n\+type "
        import_patterns = (r"\n\+import ",)
        func_rem_pattern = r"\n\-func "
        async_rem = r"(?!)"
        class_rem_pattern = r"\n\-type "
        import_rem_patterns = (r"\n\-import ",)
    elif profile.name == "rust":
        func_pattern = r"\n\+fn "
        async_func = r"\n\+async fn "
        class_pattern = r"\n\+(struct|enum|impl|trait) "
        import_patterns = (r"\n\+use ",)
        func_rem_pattern = r"\n\-fn "
        async_rem = r"\n\-async fn "
        class_rem_pattern = r"\n\-(struct|enum|impl|trait) "
        import_rem_patterns = (r"\n\-use ",)
    else:
        # Unknown language — best-effort TypeScript-style heuristics.
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
        f"{parent_commit}..{child_commit}",
        "--", ":(exclude)node_modules", ":(exclude)dist", ":(exclude).instrument", ":(exclude)__pycache__", ":(exclude).pytest_cache",
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

    Loads rules from conventions/<language>.yaml. Checks naming patterns
    (should match), forbidden patterns (should not match), and applies
    per-category weights from the YAML scoring section.
    """
    if profile is None:
        profile = detect_language(worktree)
    if profile is None:
        return 1.0, []

    rules = get_convention_rules(profile.name)
    violations: list[str] = []

    # Category scores: naming (should-match) and violations (should-not-match).
    # Only these two categories are computed. The structural conventions
    # (import_order, docstring, type_hints) declared in the YAML `conventions:`
    # list are aspirational — not yet evaluated — so their weights are omitted
    # from the rubric rather than silently un-scored (P0-9).
    naming_weight = rules.scoring.get("naming_weight", 0.5)
    violations_weight = rules.scoring.get("violations_weight", 0.5)
    total_weight = naming_weight + violations_weight or 1.0

    naming_passed = 0
    naming_total = 0
    forbidden_passed = 0
    forbidden_total = 0

    tracked = _run_git(worktree, "ls-files", "--cached", "--others", "--exclude-standard")
    _EXCLUDED_DIRS = ("node_modules/", "build/", "dist/", ".instrument/", "__pycache__/", ".pytest_cache/", "venv/", ".venv/")  # noqa: N806
    for rel_path in tracked.splitlines():
        rel_path = rel_path.strip()
        if not rel_path:
            continue
        # Skip dependency/build/generated directories — only score the model's
        # own source, not committed node_modules or compiled output.
        if rel_path.startswith(_EXCLUDED_DIRS):
            continue
        fp = worktree / rel_path
        if fp.suffix not in profile.extensions:
            continue
        try:
            content = fp.read_text()
        except (OSError, UnicodeDecodeError):
            continue

        for rule in rules.naming_patterns:
            naming_total += 1
            if re.search(rule.pattern, content, re.MULTILINE):
                naming_passed += 1
            else:
                violations.append(f"{fp.name}: {rule.description}")

        for rule in rules.forbidden_patterns:
            forbidden_total += 1
            if not re.search(rule.pattern, content, re.MULTILINE):
                forbidden_passed += 1
            else:
                violations.append(f"{fp.name}: {rule.description}")

    naming_score = naming_passed / naming_total if naming_total > 0 else 1.0
    forbidden_score = forbidden_passed / forbidden_total if forbidden_total > 0 else 1.0

    score = (
        naming_score * naming_weight + forbidden_score * violations_weight
    ) / total_weight

    return round(score, 3), violations


# ── SonarQube Delta ────────────────────────────────────────────

def compute_sonar_delta(
    worktree: Path,
    parent_commit: str,
    child_commit: str,
    *,
    sonar_url: str = os.environ.get("SONAR_URL", "http://127.0.0.1:9000"),
    sonar_token: str = "",
) -> dict[str, Any]:
    """Compute SonarQube metric deltas between two commits.

    Checks if SonarQube is reachable, and if so, runs analysis at both
    commits and computes the delta.

    Returns dict with delta values. All zero if SonarQube unavailable.
    """
    try:
        from .sonar import run_sonar_analysis
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
            # Unique project keys per story+commit — concurrent stories must not
            # collide on the default exp_{dirname} key ("parent"/"child").
            parent_key = f"exp_{worktree.name}_{parent_commit[:12]}"
            child_key = f"exp_{worktree.name}_{child_commit[:12]}"
            if sonar_token:
                parent_sm = run_sonar_analysis(
                    parent_path, sonar_url=sonar_url,
                    sonar_user=sonar_token, sonar_password="",
                    project_key=parent_key,
                )
                child_sm = run_sonar_analysis(
                    child_path, sonar_url=sonar_url,
                    sonar_user=sonar_token, sonar_password="",
                    project_key=child_key,
                )
            else:
                # Use default local-dev credentials (admin/admin)
                parent_sm = run_sonar_analysis(parent_path, sonar_url=sonar_url, project_key=parent_key)
                child_sm = run_sonar_analysis(child_path, sonar_url=sonar_url, project_key=child_key)

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


def _prescan_sonar_parallel(
    worktree: Path,
    commit_hashes: list[str],
    sonar_url: str,
    max_workers: int = 6,
) -> None:
    """Warm the sonar cache by scanning every unique commit in parallel.

    The delta loop re-runs ``run_sonar_analysis`` per commit (parent + child);
    this pre-pass scans each unique commit once — concurrently — so the delta
    loop only hits the process-local cache instead of re-launching the scanner
    (~30s each) sequentially.
    """
    from concurrent.futures import ThreadPoolExecutor

    from .sonar import run_sonar_analysis

    unique = list(dict.fromkeys(commit_hashes))
    if not unique:
        return

    def scan(commit_hash: str) -> None:
        with tempfile.TemporaryDirectory(prefix="prescan_", dir="/tmp") as tmp:
            checkout = Path(tmp) / "checkout"
            _run_git(worktree, "worktree", "add", "--detach", str(checkout), commit_hash)
            try:
                run_sonar_analysis(
                    str(checkout),
                    sonar_url=sonar_url,
                    project_key=f"exp_{worktree.name}_{commit_hash[:12]}",
                )
            finally:
                _run_git(worktree, "worktree", "remove", "--force", str(checkout))

    with ThreadPoolExecutor(max_workers=min(max_workers, len(unique))) as pool:
        list(pool.map(scan, unique))


# ── Full Commit Analysis ───────────────────────────────────────

def analyze_commit(
    worktree: Path,
    parent_commit: str,
    child_commit: str,
    session_number: int = 0,
    run_sonar: bool = False,
) -> CommitAnalysis:
    """Run all analysis layers on a single commit.

    SonarQube is opt-in (slow — two scanner runs per commit).
    """
    analysis = compute_ast_diff(worktree, parent_commit, child_commit)
    analysis.session_number = session_number

    if run_sonar:
        # SonarQube delta — returns zeros if unreachable or scanner unavailable
        sonar = compute_sonar_delta(worktree, parent_commit, child_commit)
        analysis.sonar_available = sonar.get("available", False)
        analysis.sonar_bugs_delta = sonar.get("bugs_delta", 0)
        analysis.sonar_smells_delta = sonar.get("smells_delta", 0)
        analysis.sonar_complexity_delta = sonar.get("complexity_delta", 0)
        analysis.sonar_duplications_delta = sonar.get("duplications_delta", 0.0)

    return analysis


def analyze_story_worktree(worktree: Path, run_sonar: bool = False) -> StoryAnalysis:
    """Analyze all commits in a story worktree.

    Walks the git log, finds consecutive commit pairs, and runs
    the full analysis pipeline on each. Convention scoring is done
    once at the story level (current worktree state).

    Args:
        worktree: Path to the story worktree with git history.
        run_sonar: If True, run SonarQube deltas (slow — opt-in).

    Returns:
        StoryAnalysis with per-commit results.
    """
    # Get all commit hashes in chronological order (oldest first)
    try:
        log = _run_git(worktree, "log", "--reverse", "--format=%H %s")
    except RuntimeError:
        # No commits yet (empty repo) — git log exits non-zero.
        return StoryAnalysis(story_name="unknown")
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

    # Warm the sonar cache by scanning every unique commit in parallel, so the
    # delta loop below only hits cached metrics instead of re-running the scanner.
    if run_sonar:
        _prescan_sonar_parallel(
            worktree,
            [h for h, _ in commits],
            os.environ.get("SONAR_URL", "http://127.0.0.1:9000"),
        )

    # Analyze each pair (skip seed + mutation commits, focus on session commits)
    session_num = 0
    for i in range(1, len(commits)):
        parent_hash, _ = commits[i - 1]
        child_hash, child_msg = commits[i]

        # Only analyze session commits (those from our instrument)
        if "[story]" in child_msg or "Session" in child_msg:
            session_num += 1
            analysis = analyze_commit(
                worktree, parent_hash, child_hash, session_num,
                run_sonar=run_sonar,
            )
            analysis.convention_score = final_score
            analysis.convention_violations = final_violations
            story.commits.append(analysis)

    return story


# ── Deep Quality Metrics ───────────────────────────────────────

STORY_CONSTRAINTS: dict[str, list[str]] = {
    "task_manager_api": [
        "All endpoints return JSON",
        "Use SQLite for persistence",
        "Include error handling for all endpoints",
    ],
    "static_site_gen": [
        "All output goes to ./dist by default",
        "CLI interface via commander or yargs",
        "TypeScript with strict mode enabled",
    ],
    "notification_service": [
        "All communication via WebSocket",
        "Use Redis for pub/sub and rate limiting",
        "SQLite for message persistence",
    ],
}


def _read_source_files(directory: Path, profile) -> dict[str, str]:
    """Read all source files under ``directory`` for the given language profile."""
    files: dict[str, str] = {}
    exts = set(profile.extensions) if profile else {".py", ".ts"}
    skip_parts = {".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build"}
    for ext in exts:
        if not ext.startswith("."):
            ext = "." + ext
        for f in directory.rglob(f"*{ext}"):
            if any(part in skip_parts for part in f.parts):
                continue
            try:
                files[str(f.relative_to(directory))] = f.read_text(errors="ignore")
            except OSError:
                continue
    return files


def _build_efficiency(session_token_data: list[dict], total_cost_usd: float):
    """Construct an EfficiencyMetrics from per-session token data + total cost."""
    from .efficiency import EfficiencyMetrics

    eff = EfficiencyMetrics()
    eff.total_cost_usd = total_cost_usd
    eff.cost_is_estimated = True
    for s in session_token_data:
        eff.prompt_tokens += int(s.get("prompt_tokens", 0) or 0)
        eff.completion_tokens += int(s.get("completion_tokens", 0) or 0)
        eff.reasoning_tokens += int(s.get("reasoning_tokens", 0) or 0)
        eff.total_tokens += int(s.get("total_tokens", 0) or 0)
        eff.cache_read_tokens += int(s.get("cache_read_tokens", 0) or 0)
        eff.cache_write_tokens += int(s.get("cache_write_tokens", 0) or 0)
    if eff.total_tokens:
        eff.thinking_ratio = eff.reasoning_tokens / eff.total_tokens
        eff.output_efficiency = eff.completion_tokens / eff.total_tokens
    return eff


def compute_deep_metrics(
    worktree: Path,
    *,
    story_name: str,
    model: str,
    test_passed: bool | None = None,
    total_cost_usd: float = 0.0,
    session_token_data: list[dict] | None = None,
) -> dict[str, Any]:
    """Compute LSP + solution + basin + strategy metrics for a story's final state.

    LSP diagnostics run on the final worktree state; the solution evaluator
    scores correctness / constraints / quality / novelty against the seed
    baseline; basin escape measures seed-vs-final structural divergence; and
    the strategy classifier combines those with efficiency into an archetype.
    """
    from .basin import measure_basin_escape
    from .language import detect_language
    from .lsp_diagnostics import run_diagnostics
    from .solution import evaluate_solution
    from .strategy import classify_strategy

    deep: dict[str, Any] = {}
    profile = detect_language(worktree)

    # 1. LSP diagnostics on the final state
    try:
        lsp = run_diagnostics(worktree, profile)
        deep["lsp"] = {
            "available": lsp.available,
            "tool": lsp.tool,
            "errors": lsp.errors,
            "warnings": lsp.warnings,
        }
    except Exception:
        deep["lsp"] = {"available": False, "errors": 0, "warnings": 0}

    # 2. Baseline (seed) + final code
    final_files = _read_source_files(worktree, profile)
    final_code = "\n\n".join(final_files.values())
    baseline_code = ""
    log = _run_git(worktree, "log", "--reverse", "--format=%H")
    hashes = [h for h in log.splitlines() if h]
    if hashes:
        seed_hash = hashes[0]
        with tempfile.TemporaryDirectory(prefix="deep_", dir="/tmp") as tmp:
            seed_dir = Path(tmp) / "seed"
            _run_git(worktree, "worktree", "add", "--detach", str(seed_dir), seed_hash)
            try:
                baseline_files = _read_source_files(seed_dir, profile)
                baseline_code = "\n\n".join(baseline_files.values())
            finally:
                _run_git(worktree, "worktree", "remove", "--force", str(seed_dir))

    # 3. Solution metrics
    constraints = STORY_CONSTRAINTS.get(story_name, [])
    test_results = {"story": bool(test_passed)} if test_passed is not None else None
    solution = evaluate_solution(
        final_code,
        constraints,
        test_results=test_results,
        baseline_code=baseline_code,
        code_files=final_files,
    )
    deep["solution"] = solution.to_dict()

    # 4. Basin escape (seed vs final)
    basin = measure_basin_escape(
        baseline_code,
        final_code,
        baseline_correctness=1.0,
        perturbed_correctness=solution.correctness_score,
        baseline_constraints_met=len(constraints),
        perturbed_constraints_met=solution.constraints_met,
        baseline_loc=len(baseline_code.splitlines()),
        perturbed_loc=len(final_code.splitlines()),
        model=model,
        task=story_name,
    )
    deep["basin"] = basin.to_dict()

    # 5. Efficiency + strategy
    efficiency = _build_efficiency(session_token_data or [], total_cost_usd)
    strategy = classify_strategy(basin, solution, efficiency)
    deep["strategy"] = strategy.to_dict()

    return deep


def agentic_token_dicts(sessions) -> list[dict]:
    """Extract per-session token breakdowns from SessionResult objects."""
    out: list[dict] = []
    for s in sessions:
        a = getattr(s, "agentic", None)
        if a is None:
            out.append({})
            continue
        out.append({
            k: (getattr(a, k, 0) or 0)
            for k in (
                "prompt_tokens", "completion_tokens", "reasoning_tokens",
                "total_tokens", "cache_read_tokens", "cache_write_tokens",
            )
        })
    return out


# ── Git Helpers ────────────────────────────────────────────────

def _run_git(worktree: Path, *args: str) -> str:
    """Run git in the worktree. Returns stdout. Raises on failure.

    A silent "" was previously recorded as "no change" in diff counts (P1-2).
    Fail loudly instead of emitting empty results through a value channel.
    """
    proc = subprocess.run(
        ["git"] + list(args),
        capture_output=True,
        text=True,
        cwd=str(worktree),
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (exit {proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout
