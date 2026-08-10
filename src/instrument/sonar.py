"""SonarQube static analysis for LLM-generated code quality.

Runs sonar-scanner against experiment worktrees and extracts
standardized quality metrics: bugs, vulnerabilities, code smells,
cognitive complexity, duplications, and maintainability ratings.

Provides differential quality analysis: how much did perturbation
degrade code quality beyond structural divergence?
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SONAR_URL_DEFAULT = "http://localhost:9000"
SONAR_USER_DEFAULT = "admin"    # local dev only — override via ENV for prod
SONAR_PASSWORD_DEFAULT = "admin"  # local dev only — override via ENV for prod


@dataclass
class SonarMetrics:
    """Standard SonarQube quality measures for a codebase."""

    project_key: str = ""
    analyzed: bool = False

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
    _delta = lambda b, p: max(0, p - b) if isinstance(b, int) else round(p - b, 4)

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


def run_sonar_analysis(
    worktree_path: str,
    project_key: str = "",
    sonar_url: str = SONAR_URL_DEFAULT,
    sonar_user: str = SONAR_USER_DEFAULT,
    sonar_password: str = SONAR_PASSWORD_DEFAULT,
    timeout_sec: int = 120,
) -> SonarMetrics:
    """Run sonar-scanner on a worktree and extract quality measures.

    Args:
        worktree_path: Path to the generated code directory.
        project_key: Unique SonarQube project key (defaults to worktree dir name).
        sonar_url: SonarQube server URL.
        sonar_user: SonarQube username.
        sonar_password: SonarQube password.
        timeout_sec: Maximum seconds to wait for scanner + API.

    Returns:
        SonarMetrics with extracted measures. ``analyzed`` is False if
        sonar-scanner is unavailable or the server is unreachable.
    """
    wt = Path(worktree_path)
    if not wt.exists():
        return SonarMetrics(project_key=project_key, error="worktree not found")

    if not shutil.which("sonar-scanner"):
        return SonarMetrics(project_key=project_key, error="sonar-scanner not on PATH")

    if not project_key:
        project_key = f"exp_{wt.name}"

    metrics = SonarMetrics(project_key=project_key)

    props_path = wt / "sonar-project.properties"
    props_content = f"""sonar.projectKey={project_key}
sonar.projectName={project_key}
sonar.sources=.
sonar.host.url={sonar_url}
sonar.login={sonar_user}
sonar.password={sonar_password}
sonar.exclusions=**/node_modules/**,**/__pycache__/**,**/.git/**,**/venv/**,**/.venv/**
"""
    try:
        props_path.write_text(props_content)
    except OSError:
        return SonarMetrics(project_key=project_key, error="cannot write sonar-project.properties")

    t0 = time.monotonic()
    try:
        result = subprocess.run(
            ["sonar-scanner", "-Dsonar.scanner.skipJreProvisioning=true"],
            cwd=str(wt),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
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

    return _fetch_measures(project_key, sonar_url, sonar_user, sonar_password, metrics, remaining)


def _fetch_measures(
    project_key: str,
    sonar_url: str,
    sonar_user: str,
    sonar_password: str,
    metrics: SonarMetrics,
    timeout_sec: float,
) -> SonarMetrics:
    import urllib.request
    from base64 import b64encode

    metric_keys = (
        "bugs,vulnerabilities,code_smells,cognitive_complexity,complexity,"
        "duplicated_lines_density,ncloc,comment_lines_density,classes,"
        "functions,files,sqale_rating,reliability_rating,security_rating,"
        "alert_status,sqale_index,sqale_debt_ratio"
    )
    url = f"{sonar_url}/api/measures/component?component={project_key}&metricKeys={metric_keys}"

    auth_header = b64encode(f"{sonar_user}:{sonar_password}".encode()).decode()

    deadline = time.monotonic() + min(timeout_sec, 120)
    last_error = ""

    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Basic {auth_header}")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                time.sleep(2)
                last_error = f"project {project_key} not ready yet"
                continue
            return SonarMetrics(project_key=project_key, error=f"HTTP {e.code}: {e.reason}")
        except Exception as e:
            time.sleep(2)
            last_error = str(e)[:100]
            continue

        component = data.get("component")
        if not component:
            time.sleep(2)
            continue

        measures = {m["metric"]: m.get("value", "") for m in component.get("measures", [])}

        if not measures:
            time.sleep(2)
            continue

        metrics.analyzed = True
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
        return metrics

    return SonarMetrics(project_key=project_key, error=f"API timeout: {last_error}")


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
    try:
        props_path.unlink(missing_ok=True)
    except OSError:
        pass
