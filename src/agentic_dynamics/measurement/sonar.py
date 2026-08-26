"""SonarQube static analysis for LLM-generated code quality.

Runs sonar-scanner against experiment worktrees and extracts
standardized quality metrics: bugs, vulnerabilities, code smells,
cognitive complexity, duplications, and maintainability ratings.

Provides differential quality analysis: how much did perturbation
degrade code quality beyond structural divergence?
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Measured analyzer status enum (design §5.2, hard rule 6): ``available`` — an analysis
#: exists and is known to cover the requested revision; ``unavailable`` — no analysis, no
#: scanner, or an error; ``stale-refused`` — an analysis EXISTS for the project but its
#: revision cannot be confirmed to match the requested one (fail-closed), so it is refused
#: and never stamped with the current commit.
SONAR_STATUS_AVAILABLE = "available"
SONAR_STATUS_UNAVAILABLE = "unavailable"
SONAR_STATUS_STALE_REFUSED = "stale-refused"

SONAR_URL_DEFAULT = os.environ.get("SONAR_URL", "http://localhost:9000")
SONAR_USER_DEFAULT = "admin"    # local dev only — override via ENV for prod
SONAR_PASSWORD_DEFAULT = "admin"  # local dev only — override via ENV for prod

# Known sonar-scanner install locations (checked when not on PATH).
_SONAR_SCANNER_CANDIDATES = [
    "/usr/local/bin/sonar-scanner",
    "/opt/sonar-scanner/bin/sonar-scanner",
    "/opt/sonar-scanner-*/bin/sonar-scanner",
]

# Process-local cache keyed by project key. A commit is scanned twice (once as
# the child of its session, once as the parent of the next), so this halves the
# number of scanner runs. Safe because project keys embed the commit hash.
_SONAR_CACHE: dict[str, SonarMetrics] = {}


def _find_sonar_scanner() -> str | None:
    """Locate the sonar-scanner executable, falling back to known paths."""
    found = shutil.which("sonar-scanner")
    if found:
        return found
    import glob
    for candidate in _SONAR_SCANNER_CANDIDATES:
        matches = glob.glob(candidate)
        for m in matches:
            if os.path.isfile(m) and os.access(m, os.X_OK):
                return m
    # Last resort: any sonar-scanner under /tmp (bundled installs)
    for m in glob.glob("/tmp/sonar-scanner*/bin/sonar-scanner"):
        if os.path.isfile(m) and os.access(m, os.X_OK):
            return m
    return None


def _find_java() -> str | None:
    """Locate a java executable, preferring a bundled JRE next to the scanner."""
    scanner = _find_sonar_scanner()
    if scanner:
        jre = Path(scanner).resolve().parent.parent / "jre" / "bin" / "java"
        if jre.is_file() and os.access(jre, os.X_OK):
            return str(jre)
    return shutil.which("java")


def _scanner_env() -> dict:
    """Build subprocess env with JAVA_HOME resolved for the scanner."""
    env = os.environ.copy()
    java = _find_java()
    if java:
        env["JAVA_HOME"] = str(Path(java).resolve().parent.parent)
    return env


@dataclass
class SonarMetrics:
    """Standard SonarQube quality measures for a codebase.

    Revision identity (design §5.2): ``analyzed_sha`` is the revision the analysis actually
    covers — ``""`` when the server did not record it (``sonar.scm.disabled=true``) or when a
    fetch could not confirm it. ``status`` is the measured analyzer-status enum
    (``available`` / ``unavailable`` / ``stale-refused``); a ``stale-refused`` result carries
    the (stale) measures but is never stamped with the current commit. ``tool_version`` /
    ``config_hash`` are recorded when a fresh scan runs (the scanner version and the sha256 of
    the ``sonar-project.properties`` it used); they stay ``""`` when unknowable — never
    fabricated.
    """

    project_key: str = ""
    analyzed: bool = False

    #: Revision identity + analyzer metadata (typed JSON payload consumers).
    status: str = SONAR_STATUS_UNAVAILABLE
    analyzed_sha: str = ""
    tool_version: str = ""
    config_hash: str = ""
    coverage: float = 0.0

    bugs: int = 0
    vulnerabilities: int = 0
    code_smells: int = 0
    cognitive_complexity: int = 0
    complexity: int = 0
    duplicated_lines_density: float = 0.0
    ncloc: int = 0
    comment_lines_density: float = 0.0
    classes: int = 0
    functions: int = 0
    files: int = 0

    maintainability_rating: str = ""
    reliability_rating: str = ""
    security_rating: str = ""
    quality_gate: str = ""

    sqale_index: int = 0
    sqale_debt_ratio: float = 0.0

    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "analyzed": self.analyzed,
            "status": self.status,
            "analyzed_sha": self.analyzed_sha,
            "tool_version": self.tool_version,
            "config_hash": self.config_hash,
            "coverage": round(self.coverage, 1),
            "bugs": self.bugs,
            "vulnerabilities": self.vulnerabilities,
            "code_smells": self.code_smells,
            "cognitive_complexity": self.cognitive_complexity,
            "complexity": self.complexity,
            "duplicated_lines_density": round(self.duplicated_lines_density, 1),
            "ncloc": self.ncloc,
            "comment_lines_density": round(self.comment_lines_density, 1),
            "classes": self.classes,
            "functions": self.functions,
            "files": self.files,
            "maintainability_rating": self.maintainability_rating,
            "reliability_rating": self.reliability_rating,
            "security_rating": self.security_rating,
            "quality_gate": self.quality_gate,
            "sqale_index": self.sqale_index,
            "sqale_debt_ratio": round(self.sqale_debt_ratio, 1),
        }


def compute_sonar_diff(baseline: SonarMetrics, perturbed: SonarMetrics) -> dict[str, Any]:
    """Compute quality degradation deltas between baseline and perturbed runs.

    Returns a dict suitable for merging into BasinMetrics or results JSON.
    """
    def _delta(b, p):
        return max(0, p - b) if isinstance(b, int) else round(p - b, 4)

    b_r = _rating_value(baseline.maintainability_rating)
    p_r = _rating_value(perturbed.maintainability_rating)

    return {
        "sonar_bugs_delta": _delta(baseline.bugs, perturbed.bugs),
        "sonar_vulnerabilities_delta": _delta(baseline.vulnerabilities, perturbed.vulnerabilities),
        "sonar_code_smells_delta": _delta(baseline.code_smells, perturbed.code_smells),
        "sonar_cognitive_complexity_delta": _delta(baseline.cognitive_complexity, perturbed.cognitive_complexity),
        "sonar_complexity_delta": _delta(baseline.complexity, perturbed.complexity),
        "sonar_duplication_delta": _delta(baseline.duplicated_lines_density, perturbed.duplicated_lines_density),
        "sonar_maintainability_delta": p_r - b_r,
        "sonar_reliability_delta": _rating_value(perturbed.reliability_rating) - _rating_value(baseline.reliability_rating),
        "sonar_security_delta": _rating_value(perturbed.security_rating) - _rating_value(baseline.security_rating),
        "sonar_baseline_bugs": baseline.bugs,
        "sonar_baseline_smells": baseline.code_smells,
        "sonar_perturbed_bugs": perturbed.bugs,
        "sonar_perturbed_smells": perturbed.code_smells,
    }


def project_key_for(worktree_path: str | Path, revision: str = "") -> str:
    """The project key the scanner uses for a worktree (the one place the rule is defined).

    ``base_key`` is the worktree dir name, prefixed ``exp_`` unless it already carries an
    ``exp_``/``story_`` prefix; a ``revision`` scopes the key to that revision
    (``<base>_<rev[:12]>``) so a fetch for the key can only ever return that revision's
    analysis. :func:`run_sonar_analysis` uses this to compute its default key; the v2
    before/after seam (``runtime.workflow_runner._sonar_evidence``) uses it to keep the parent
    and phase revision keys consistent even when the parent is scanned from a temp checkout.
    """
    wt = Path(worktree_path)
    base_key = wt.name if wt.name.startswith(("exp_", "story_")) else f"exp_{wt.name}"
    if revision:
        return f"{base_key}_{revision[:12]}"
    return base_key


def run_sonar_analysis(
    worktree_path: str,
    project_key: str = "",
    revision: str = "",
    sonar_url: str = SONAR_URL_DEFAULT,
    sonar_user: str = SONAR_USER_DEFAULT,
    sonar_password: str = SONAR_PASSWORD_DEFAULT,
    timeout_sec: int = 300,
) -> SonarMetrics:
    """Run sonar-scanner on a worktree and extract quality measures.

    Fetch-first: if the project was already analyzed (server retains
    analyses indefinitely), the cached measures are fetched directly and
    the scanner is skipped. Otherwise the scanner runs, then measures are
    fetched from the API.

    Revision identity (design §5.2): when ``revision`` is supplied and no explicit
    ``project_key`` is, the key is revision-scoped (``<base>_<revision[:12]>``), so a fetch
    for that key can only ever return that revision's analysis. A fetch-first result whose
    analysis revision cannot be CONFIRMED to match the requested ``revision`` is REFUSED —
    the returned :class:`SonarMetrics` carries ``status="stale-refused"`` and the true
    (or unrecorded) ``analyzed_sha``, and is never stamped with the current commit.
    Confirmation is established by (a) the revision-scoped key contract, or (b) the server
    recording the matching revision in the analysis metadata. Legacy callers that pass no
    ``revision`` keep the old unscoped fetch-first behavior (``status="available"``).

    Args:
        worktree_path: Path to the generated code directory.
        project_key: Unique SonarQube project key (defaults to worktree dir name, scoped by
            ``revision`` when one is supplied).
        revision: The git commit sha the analysis is expected to cover. Folded into the
            project key when no explicit ``project_key`` is given.
        sonar_url: SonarQube server URL.
        sonar_user: SonarQube username.
        sonar_password: SonarQube password.
        timeout_sec: Maximum seconds to wait for scanner + API.

    Returns:
        SonarMetrics with extracted measures. ``analyzed`` is False and ``status`` is
        ``unavailable`` if the server is unreachable and no cached analysis exists;
        ``status`` is ``stale-refused`` if an analysis exists but its revision cannot be
        confirmed to match ``revision``.
    """
    wt = Path(worktree_path)
    if not wt.exists():
        return SonarMetrics(project_key=project_key, error="worktree not found")

    project_key = project_key or project_key_for(wt, revision)

    if project_key in _SONAR_CACHE:
        return _SONAR_CACHE[project_key]

    # Fetch-first: reuse a cached server-side analysis instead of re-running
    # the (expensive) scanner. Returns None only when no analysis exists yet.
    existing = _fetch_once(project_key, sonar_url, sonar_user, sonar_password)
    if existing is not None:
        existing.analyzed_sha = _fetch_analyzed_revision(
            project_key, sonar_url, sonar_user, sonar_password
        )
        # A revision-scoped key (built from ``revision``) is, by construction, that revision's
        # analysis even when the server recorded no SCM revision; record it as such.
        if not existing.analyzed_sha and revision and revision[:12] in project_key:
            existing.analyzed_sha = revision
        # Refusal: a revision was requested and the analysis cannot be confirmed to cover it.
        # Fail-closed — an unrecorded revision (scm disabled) confirms nothing.
        if revision and not _revision_confirmed(revision, existing.analyzed_sha, project_key):
            existing.status = SONAR_STATUS_STALE_REFUSED
        else:
            existing.status = SONAR_STATUS_AVAILABLE
        _SONAR_CACHE[project_key] = existing
        return existing

    scanner = _find_sonar_scanner()
    if not scanner:
        return SonarMetrics(project_key=project_key, error="sonar-scanner not on PATH")

    props_path = wt / "sonar-project.properties"
    props_content = f"""sonar.projectKey={project_key}
sonar.projectName={project_key}
sonar.sources=.
sonar.host.url={sonar_url}
sonar.login={sonar_user}
sonar.password={sonar_password}
sonar.exclusions=**/node_modules/**,**/__pycache__/**,**/.git/**,**/venv/**,**/.venv/**
sonar.scm.disabled=true
"""
    try:
        props_path.write_text(props_content)
    except OSError:
        return SonarMetrics(project_key=project_key, error="cannot write sonar-project.properties")

    t0 = time.monotonic()
    try:
        result = subprocess.run(
            [scanner, "-Dsonar.scanner.javaOpts=-Xmx512m -XX:+UseSerialGC -XX:TieredStopAtLevel=1"],
            cwd=str(wt),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=_scanner_env(),
        )
    except subprocess.TimeoutExpired:
        _cleanup(props_path)
        return SonarMetrics(project_key=project_key, error="sonar-scanner timed out")
    except OSError:
        _cleanup(props_path)
        return SonarMetrics(project_key=project_key, error="sonar-scanner execution failed")
    finally:
        pass

    _cleanup(props_path)

    elapsed = time.monotonic() - t0

    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "")[:200]
        return SonarMetrics(project_key=project_key, error=f"sonar-scanner failed: {stderr}")

    remaining = timeout_sec - elapsed
    if remaining < 2:
        return SonarMetrics(project_key=project_key, error="no time remaining for API fetch")

    result = _fetch_measures(project_key, sonar_url, sonar_user, sonar_password, remaining)
    if result.analyzed:
        # A fresh scan under a revision-scoped (or caller-provided commit-scoped) key covers
        # exactly the worktree/revision we scanned. The config the analysis used is the props
        # we just wrote; the tool version is the scanner's.
        result.status = SONAR_STATUS_AVAILABLE
        result.analyzed_sha = revision
        result.config_hash = hashlib.sha256(props_content.encode()).hexdigest()
        result.tool_version = _scanner_version()
        _SONAR_CACHE[project_key] = result
    else:
        result.status = SONAR_STATUS_UNAVAILABLE
    return result


def _parse_measures(project_key: str, measures: dict) -> SonarMetrics:
    """Populate a SonarMetrics from a raw measures dict (keys are metric names)."""
    metrics = SonarMetrics(project_key=project_key, analyzed=True)
    metrics.bugs = _int_val(measures, "bugs")
    metrics.vulnerabilities = _int_val(measures, "vulnerabilities")
    metrics.code_smells = _int_val(measures, "code_smells")
    metrics.cognitive_complexity = _int_val(measures, "cognitive_complexity")
    metrics.complexity = _int_val(measures, "complexity")
    metrics.duplicated_lines_density = _float_val(measures, "duplicated_lines_density")
    metrics.ncloc = _int_val(measures, "ncloc")
    metrics.comment_lines_density = _float_val(measures, "comment_lines_density")
    metrics.classes = _int_val(measures, "classes")
    metrics.functions = _int_val(measures, "functions")
    metrics.files = _int_val(measures, "files")
    metrics.maintainability_rating = _rating_label(measures.get("sqale_rating", ""))
    metrics.reliability_rating = _rating_label(measures.get("reliability_rating", ""))
    metrics.security_rating = _rating_label(measures.get("security_rating", ""))
    metrics.quality_gate = measures.get("alert_status", "")
    metrics.sqale_index = _int_val(measures, "sqale_index")
    metrics.sqale_debt_ratio = _float_val(measures, "sqale_debt_ratio")
    metrics.coverage = _float_val(measures, "coverage")
    return metrics


_METRIC_KEYS = (
    "bugs,vulnerabilities,code_smells,cognitive_complexity,complexity,"
    "duplicated_lines_density,ncloc,comment_lines_density,classes,"
    "functions,files,sqale_rating,reliability_rating,security_rating,"
    "alert_status,sqale_index,sqale_debt_ratio,coverage"
)


def _fetch_once(
    project_key: str,
    sonar_url: str,
    sonar_user: str,
    sonar_password: str,
) -> SonarMetrics | None:
    """Single-attempt fetch of cached measures for a project.

    Returns a populated SonarMetrics if the project has an analysis,
    else None (no analysis yet / unreachable). Does not retry.
    """
    import urllib.request
    from base64 import b64encode

    url = f"{sonar_url}/api/measures/component?component={project_key}&metricKeys={_METRIC_KEYS}"
    auth_header = b64encode(f"{sonar_user}:{sonar_password}".encode()).decode()
    try:
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Basic {auth_header}")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None

    component = data.get("component")
    if not component:
        return None
    measures = {m["metric"]: m.get("value", "") for m in component.get("measures", [])}
    if not measures:
        return None
    return _parse_measures(project_key, measures)


def _fetch_measures(
    project_key: str,
    sonar_url: str,
    sonar_user: str,
    sonar_password: str,
    timeout_sec: float,
) -> SonarMetrics:
    """Fetch measures with retries, waiting for a just-submitted analysis."""
    deadline = time.monotonic() + min(timeout_sec, 120)
    last_error = ""

    while time.monotonic() < deadline:
        fetched = _fetch_once(project_key, sonar_url, sonar_user, sonar_password)
        if fetched is not None:
            return fetched
        time.sleep(2)
        last_error = f"project {project_key} not ready yet"

    return SonarMetrics(project_key=project_key, error=f"API timeout: {last_error}")


def _fetch_analyzed_revision(
    project_key: str,
    sonar_url: str,
    sonar_user: str,
    sonar_password: str,
) -> str:
    """Return the SCM revision recorded for the project's most recent analysis.

    Queries ``/api/project_analyses/search``; returns ``""`` when the server recorded no
    revision (``sonar.scm.disabled=true``) or when the API is unreachable — an unrecorded
    revision confirms nothing, so callers fail closed.
    """
    import urllib.request
    from base64 import b64encode

    url = f"{sonar_url}/api/project_analyses/search?project={project_key}&ps=1"
    auth_header = b64encode(f"{sonar_user}:{sonar_password}".encode()).decode()
    try:
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Basic {auth_header}")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return ""
    analyses = data.get("analyses") or []
    if not analyses:
        return ""
    return analyses[0].get("revision") or ""


def _revision_confirmed(requested: str, captured: str, project_key: str) -> bool:
    """Return True iff a fetched analysis is known to cover ``requested``.

    Confirmed when (a) the project key embeds the requested revision prefix (the
    revision-scoped key contract — an analysis under ``exp_<name>_<rev[:12]>`` was produced
    by scanning that revision's tree) or (b) the server recorded the exact matching revision
    in the analysis metadata. Fail-closed: an unscoped key with a missing or different
    captured revision is NOT confirmed.
    """
    if not requested:
        return True
    if requested[:12] in project_key:
        return True
    return bool(captured) and captured == requested


def _scanner_version() -> str:
    """Return the sonar-scanner version string, or ``""`` when it cannot be determined."""
    scanner = _find_sonar_scanner()
    if not scanner:
        return ""
    try:
        proc = subprocess.run(
            [scanner, "-v"], capture_output=True, text=True, timeout=15
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""
    text = (proc.stdout or "") + (proc.stderr or "")
    match = re.search(r"SonarScanner(?:\s+CLI)?\s+([\d.]+)", text)
    return match.group(1) if match else ""


@dataclass
class SonarIssue:
    """One SonarQube issue (issue-level record surface, design §5.4)."""

    key: str = ""
    rule: str = ""
    severity: str = ""
    message: str = ""
    file_path: str = ""  # repo-relative path (component minus the project-key prefix)
    line: int = 0  # 0 for project-level issues
    effort: str = ""  # remediation effort, e.g. "5min"
    status: str = ""  # e.g. "OPEN"

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "file_path": self.file_path,
            "line": self.line,
            "effort": self.effort,
            "status": self.status,
        }


def issue_identity(issue: SonarIssue) -> tuple[str, str, int]:
    """The ``(rule, file_path, line)`` identity for change-introduced novelty (design §RC2).

    Two issues are "the same" iff they share rule, repo-relative file path, and line. This is
    the identity the v2 reducer's ``new_sonar_critical_count`` uses to decide whether an issue
    in the after-analysis is NEW (absent from the before-analysis) rather than pre-existing.
    """
    return (issue.rule, issue.file_path, issue.line)


def new_issue_count(before: list[SonarIssue], after: list[SonarIssue]) -> int:
    """Change-introduced issue count: ``|{identity(after)} − {identity(before)}|``.

    A pre-existing issue (same identity in both analyses) never counts; an issue present only
    in the after-analysis counts once. Pure and deterministic — the caller decides which
    severity filter to apply by passing an already-filtered ``after``/``before`` (see
    :func:`fetch_sonar_issues`'s ``severities`` param).
    """
    before_ids = {issue_identity(i) for i in before}
    return sum(1 for i in after if issue_identity(i) not in before_ids)


def fetch_sonar_issues(
    project_key: str,
    sonar_url: str = SONAR_URL_DEFAULT,
    sonar_user: str = SONAR_USER_DEFAULT,
    sonar_password: str = SONAR_PASSWORD_DEFAULT,
    *,
    ps: int = 500,
    severities: str = "",
) -> list[SonarIssue]:
    """Fetch one :class:`SonarIssue` per line/rule from ``/api/issues/search``.

    ``severities`` is a comma-separated server-side filter (e.g. ``"BLOCKER,CRITICAL"``); when
    non-empty it is passed through as the ``severities`` query param so the server returns only
    issues at those severities (design §RC1 — the v2 severity filter). Paged to ``ps`` (capped
    at the API's 500). Returns ``[]`` on any API failure — an absent issue surface stays
    absent, never fabricated.
    """
    import urllib.request
    from base64 import b64encode

    auth_header = b64encode(f"{sonar_user}:{sonar_password}".encode()).decode()
    issues: list[SonarIssue] = []
    page = 1
    page_size = min(max(ps, 1), 500)
    while True:
        url = (
            f"{sonar_url}/api/issues/search?componentKeys={project_key}"
            f"&ps={page_size}&p={page}"
        )
        if severities:
            url += f"&severities={severities}"
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Basic {auth_header}")
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
        except Exception:
            return issues
        batch = data.get("issues") or []
        for item in batch:
            component = item.get("component", "")
            file_path = component.split(":", 1)[1] if ":" in component else component
            line = item.get("line") or ((item.get("textRange") or {}).get("startLine") or 0)
            issues.append(
                SonarIssue(
                    key=item.get("key", ""),
                    rule=item.get("rule", ""),
                    severity=item.get("severity", ""),
                    message=item.get("message", ""),
                    file_path=file_path,
                    line=line,
                    effort=item.get("effort", ""),
                    status=item.get("status", ""),
                )
            )
        total = data.get("paging", {}).get("total", 0)
        if not batch or page * page_size >= total:
            return issues
        page += 1


def sonar_quality_score(sonar: SonarMetrics) -> float:
    """Composite sonar quality score 0-1 based on ratings and issue density.

    Higher = better. Combines maintainability, reliability, security ratings
    with bugs density and code smells density.
    """
    if not sonar.analyzed or sonar.ncloc == 0:
        return 0.5

    rating_scores = {
        "A": 1.0, "B": 0.8, "C": 0.6, "D": 0.4, "E": 0.2, "": 0.5,
    }

    r = (
        0.35 * rating_scores.get(sonar.maintainability_rating, 0.5)
        + 0.25 * rating_scores.get(sonar.reliability_rating, 0.5)
        + 0.25 * rating_scores.get(sonar.security_rating, 0.5)
        + 0.15 * (1.0 if sonar.quality_gate.upper() == "OK" else 0.0)
    )

    bugs_per_kloc = (sonar.bugs / max(sonar.ncloc, 1)) * 1000
    smells_per_kloc = (sonar.code_smells / max(sonar.ncloc, 1)) * 1000

    bugs_factor = max(0, 1.0 - bugs_per_kloc / 10.0)
    smells_factor = max(0, 1.0 - smells_per_kloc / 50.0)
    dup_factor = max(0, 1.0 - sonar.duplicated_lines_density / 20.0)

    density_score = (bugs_factor + smells_factor + dup_factor) / 3.0

    return 0.6 * r + 0.4 * density_score


def _rating_value(rating: str) -> int:
    return {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}.get(rating.upper(), 0)


def _rating_label(val: str) -> str:
    try:
        return {1: "A", 2: "B", 3: "C", 4: "D", 5: "E"}.get(int(val), "")
    except (ValueError, TypeError):
        return ""


def _int_val(measures: dict, key: str) -> int:
    try:
        return int(measures.get(key, 0))
    except (ValueError, TypeError):
        return 0


def _float_val(measures: dict, key: str) -> float:
    try:
        return float(measures.get(key, 0))
    except (ValueError, TypeError):
        return 0.0


def _cleanup(props_path: Path) -> None:
    with contextlib.suppress(OSError):
        props_path.unlink(missing_ok=True)
