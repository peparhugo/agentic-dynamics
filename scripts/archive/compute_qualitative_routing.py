"""compute_qualitative_routing.py — p1 of the qualitative-routing-analysis workflow.

Turn the qualitative review corpus into per-model PROFILES + a COVERAGE table + the
computable CORRELATIONS. This is the corpus computation, BOUNDED to the numbers: it reads
the review/analysis/story files, derives the per-model qualitative texture, and writes a
reproducible JSON + CSVs under ``experiments/results/qualitative_routing/``. It does NOT
interpret the numbers and does NOT write the findings (that is p2).

Corpus (read-only):
    experiments/results/reviews/review_*.json        — flash-authored commit reviews
    experiments/results/reviews_blind/*.json          — blind reviews (model field '?' / unknown)
    experiments/results/analysis/analysis_*.json      — per-story post-hoc analysis
    experiments/results/stories/**/*.json             — story results (subject model, condition)

Key semantic fact the whole computation rests on (verified against the corpus):
    the review file's top-level ``model`` field is the REVIEWER model — ``review_all.py``
    hard-codes ``MODEL = "deepseek/deepseek-v4-flash"`` — NOT the subject model. The subject
    model (the model whose work is reviewed) is recovered by joining ``review.story_id`` to
    the story result's ``model`` field. The reviewer-model bias (flash reviews flash, and
    flash reviews everyone else) is therefore a property of every row below, and is surfaced
    as ``reviewer_model`` everywhere rather than silently conflated with the subject.

Usage:
    python3 scripts/archive/compute_qualitative_routing.py [--out-dir DIR] [--dry-run]

Output (under ``experiments/results/qualitative_routing/`` by default):
    qualitative_routing_compute.json   — the full derived result
    coverage_table.csv                 — per-model coverage table
    per_model_profiles.csv             — per-model numeric texture
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import numpy as np  # noqa: E402
    from scipy import stats  # noqa: E402
except ImportError:  # pragma: no cover — numpy/scipy are pinned in pyproject.toml
    np = None
    stats = None


# ─────────────────────────────────────────────────────────────────────────────
# Paths and corpus enumeration
# ─────────────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS = REPO_ROOT / "experiments" / "results"
REVIEWS_DIR = RESULTS / "reviews"
BLIND_DIR = RESULTS / "reviews_blind"
ANALYSIS_DIR = RESULTS / "analysis"
STORIES_DIR = RESULTS / "stories"
OUT_DIR = RESULTS / "qualitative_routing"

# The seven canonical subject models (the story corpus uses these exact ids).
CANONICAL_MODELS = [
    "deepseek/deepseek-v4-flash",
    "deepseek/deepseek-v4-pro",
    "openai/gpt-5.6-luna",
    "openai/gpt-5.6-sol",
    "openai/gpt-5.6-terra",
    "anthropic/claude-haiku-4-5",
    "anthropic/claude-sonnet-5",
]

# ─────────────────────────────────────────────────────────────────────────────
# Disclosed theme-matching patterns (methodology, hard rule 3)
# ─────────────────────────────────────────────────────────────────────────────
# A problem/strength/summary text is matched against these keyword patterns,
# case-insensitively, as substring regexes. A problem may match several themes;
# the per-theme rate is therefore non-exclusive. Limits (disclosed honestly):
#   * keyword matching has false positives (e.g. "scope" in "scoped") and false
#     negatives (a reviewer phrase we did not anticipate) — these are HEURISTIC
#     buckets over free text, not a taxonomy.
#   * the blind reviews' problems are plain strings (no category/severity); the
#     flash reviews' problems are {category, severity, description} dicts. The
#     theme match runs over the *text* of either shape, so it is comparable.
#   * "wrong-approach" overlaps "scope" (a wholesale rewrite is both) — the
#     rates are intentionally non-exclusive and must not be summed to a total.

THEME_PATTERNS: dict[str, list[str]] = {
    "hygiene/cleanup": [
        r"\.gitignore", r"node_modules", r"\bdist\b", r"cleanup", r"hygiene",
        r"unused", r"dead code", r"duplication", r"duplicated", r"smell",
        r"deprecated", r"lockfile", r"committed\b", r"leftover", r"stale",
    ],
    "scope": [
        r"scope creep", r"out of scope", r"beyond the scope", r"scope",
        r"greenfield", r"wholesale", r"unrelated", r"throwaway", r"dead-end",
        r"rewrite", r"bloat",
    ],
    "no-op": [
        r"no changes", r"no-op", r"noop", r"empty commit", r"nothing changed",
        r"does nothing", r"no effect",
    ],
    "timeout": [
        r"timeout", r"timed out", r"hang", r"stall", r"deadlock", r"blocking the event loop",
    ],
    "spec-drift": [
        r"off-spec", r"spec drift", r"drift", r"deviate", r"does not match the spec",
        r"missing requirement", r"not in the spec", r"contradicts the spec",
        r"unrequested", r"requirement\b",
    ],
    "tests": [
        r"test", r"coverage", r"untested", r"pytest", r"jest", r"assertion",
        r"no test", r"test suite",
    ],
    "wrong-approach": [
        r"wrong approach", r"wrong-approach", r"incorrect approach", r"misguided",
        r"misconceiv", r"should instead", r"rethink", r"replaced the", r"discards the",
        r"wholesale-replaced", r"anti-pattern", r"mis-", r"misapply",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# Corpus loading
# ─────────────────────────────────────────────────────────────────────────────


def _read_json(path: Path) -> dict | None:
    """Read one JSON file; return ``None`` on any parse/IO error (recorded, never raised)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _load_story_index() -> dict[str, dict]:
    """Build ``story_id -> story`` over every story result file (recursive glob)."""
    index: dict[str, dict] = {}
    for path in sorted(STORIES_DIR.rglob("*.json")):
        story = _read_json(path)
        if not story:
            continue
        sid = story.get("story_id")
        if sid:
            index[sid] = story
    return index


def _load_reviews() -> tuple[list[dict], list[dict], list[dict]]:
    """Load every review file, split into flash / blind / '?'-model.

    Returns ``(flash_reviews, blind_reviews, question_files)`` where:
      * ``flash_reviews``  — files under ``reviews/`` (model field == flash reviewer).
      * ``blind_reviews``  — files under ``reviews_blind/`` with ``model == "unknown"``.
      * ``question_files`` — the '?'-model files: ``reviews_blind/`` with ``model``
        missing (None). These are recorded exactly (hard rule 4).
    """
    flash: list[dict] = []
    blind: list[dict] = []
    question: list[dict] = []
    for path in sorted(REVIEWS_DIR.glob("review_*.json")):
        review = _read_json(path)
        if review is not None:
            review["_file"] = path.name
            flash.append(review)
    for path in sorted(BLIND_DIR.glob("*.json")):
        review = _read_json(path)
        if review is None:
            continue
        review["_file"] = path.name
        if review.get("model") is None:
            question.append(review)
        else:
            blind.append(review)
    return flash, blind, question


def _load_analysis_index() -> dict[str, dict]:
    """Build ``story_id -> analysis`` over the post-hoc analysis files."""
    index: dict[str, dict] = {}
    for path in sorted(ANALYSIS_DIR.glob("analysis_*.json")):
        analysis = _read_json(path)
        if not analysis:
            continue
        sid = analysis.get("story_id")
        if sid:
            index[sid] = analysis
    return index


# ─────────────────────────────────────────────────────────────────────────────
# Theme matching
# ─────────────────────────────────────────────────────────────────────────────

#: Pre-compiled theme regexes (case-insensitive).
_COMPILED_THEMES: dict[str, list[re.Pattern]] = {
    theme: [re.compile(p, re.IGNORECASE) for p in patterns]
    for theme, patterns in THEME_PATTERNS.items()
}


def _match_themes(text: str) -> set[str]:
    """Return the set of theme names whose patterns match ``text`` (case-insensitive)."""
    if not text:
        return set()
    return {theme for theme, patterns in _COMPILED_THEMES.items()
            if any(p.search(text) for p in patterns)}


def _problem_text(problem) -> str:
    """Normalise a problem (dict or string) to its matchable text."""
    if isinstance(problem, dict):
        # category and description both contribute (category is a strong hint).
        return f"{problem.get('category', '')} {problem.get('description', '')}"
    return str(problem)


# ─────────────────────────────────────────────────────────────────────────────
# Per-subject-model profile derivation
# ─────────────────────────────────────────────────────────────────────────────


def _subject_model(review: dict, story_index: dict[str, dict]) -> str:
    """Resolve the SUBJECT model for a review via ``story_id -> story.model``.

    The review's own ``model`` field is the reviewer (flash); the subject model is the
    story's model. A review whose story file is absent is ``"unknown"`` (an orphan
    review — part of the coverage tail).
    """
    sid = review.get("story_id")
    story = story_index.get(sid) if sid else None
    if story is None:
        return "unknown"
    return story.get("model") or "unknown"


def _derive_profiles(
    flash: list[dict], blind: list[dict], question: list[dict], story_index: dict[str, dict]
) -> dict:
    """Derive the per-subject-model qualitative profile from every commit review.

    Numeric texture per model: mean architectural_fit, mean convention_adherence,
    debt rate (P(introduces_technical_debt)), better/worse distribution. Problem theme
    distribution over the disclosed keyword patterns. Strengths themes and top summary
    texts are captured raw for p2's sample-read.
    """
    profiles: dict[str, dict] = defaultdict(
        lambda: {
            "review_files": 0,
            "commit_reviews": 0,
            "architectural_fit": [],
            "convention_adherence": [],
            "debt_count": 0,
            "better_or_worse": Counter(),
            "problem_themes": Counter(),
            "problem_categories": Counter(),
            "strength_themes": Counter(),
            "commit_summaries": [],
            "story_summaries": [],
        }
    )
    # reviews with no subject story at all -> the '?'/orphan bucket.
    for review in flash + blind + question:
        subject = _subject_model(review, story_index)
        profile = profiles[subject]
        profile["review_files"] += 1
        reviewer_models: Counter = Counter()
        for cr in review.get("commit_reviews", []) or []:
            profile["commit_reviews"] += 1
            reviewer_models[cr.get("reviewer_model", "unknown")] += 1
            af = cr.get("architectural_fit")
            ca = cr.get("convention_adherence")
            if isinstance(af, (int, float)):
                profile["architectural_fit"].append(float(af))
            if isinstance(ca, (int, float)):
                profile["convention_adherence"].append(float(ca))
            if cr.get("introduces_technical_debt"):
                profile["debt_count"] += 1
            profile["better_or_worse"][cr.get("better_or_worse", "unknown")] += 1
            for problem in cr.get("problems", []) or []:
                text = _problem_text(problem)
                if isinstance(problem, dict):
                    profile["problem_categories"][problem.get("category", "other")] += 1
                for theme in _match_themes(text):
                    profile["problem_themes"][theme] += 1
            for strength in cr.get("strengths", []) or []:
                for theme in _match_themes(str(strength)):
                    profile["strength_themes"][theme] += 1
            if cr.get("summary"):
                profile["commit_summaries"].append(str(cr["summary"]))
        sr = review.get("story_review") or {}
        if sr.get("summary"):
            profile["story_summaries"].append(str(sr["summary"]))
        # record the reviewer-model distribution for the bias disclosure.
        profile.setdefault("reviewer_models", Counter()).update(reviewer_models)
    return profiles


def _rollup_profile(profile: dict) -> dict:
    """Aggregate a profile's collected raw lists into the numeric-texture summary."""
    af = profile["architectural_fit"]
    ca = profile["convention_adherence"]
    n = profile["commit_reviews"]
    def _mean(xs):
        return round(float(np.mean(xs)), 4) if xs else None
    return {
        "review_files": profile["review_files"],
        "commit_reviews": n,
        "mean_architectural_fit": _mean(af),
        "mean_convention_adherence": _mean(ca),
        "debt_rate": round(profile["debt_count"] / n, 4) if n else None,
        "better_or_worse": dict(profile["better_or_worse"]),
        "problem_themes": dict(profile["problem_themes"]),
        "problem_categories": dict(profile["problem_categories"]),
        "strength_themes": dict(profile["strength_themes"]),
        "reviewer_models": dict(profile.get("reviewer_models", {})),
    }


def _top_summaries(profile: dict, top_n: int = 5) -> dict:
    """Select the ``top_n`` longest commit + story summaries per model for p2's sample-read."""
    def _longest(items, k):
        return sorted((s for s in items if s), key=len, reverse=True)[:k]
    return {
        "commit_summaries": _longest(profile["commit_summaries"], top_n),
        "story_summaries": _longest(profile["story_summaries"], 3),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Coverage table
# ─────────────────────────────────────────────────────────────────────────────


def _derive_coverage(
    story_index: dict[str, dict], analysis_index: dict[str, dict],
    flash: list[dict], blind: list[dict], question: list[dict],
) -> dict:
    """Derive the per-model coverage table: stories | analyzed | reviewed | uncovered.

    Definitions (disclosed): a story is *analyzed* when an ``analysis_<story_id>.json``
    exists; *reviewed* when any review file (flash or blind) references its story_id;
    *uncovered* when no review file references it. The '?'-model files and the orphan
    reviews (reviews whose story file is absent) are reported separately as the
    coverage tail.
    """
    review_ids = {r.get("story_id") for r in flash + blind + question}
    rows: dict[str, dict] = {}
    for model in CANONICAL_MODELS:
        rows[model] = {"stories": 0, "analyzed": 0, "reviewed": 0, "uncovered": []}
    for sid, story in story_index.items():
        model = story.get("model") or "unknown"
        bucket = rows.setdefault(
            model,
            {"stories": 0, "analyzed": 0, "reviewed": 0, "uncovered": []},
        )
        bucket["stories"] += 1
        if sid in analysis_index:
            bucket["analyzed"] += 1
        if sid in review_ids:
            bucket["reviewed"] += 1
        else:
            bucket["uncovered"].append(sid)

    orphan_reviews = [
        r.get("story_id") for r in flash + blind + question
        if r.get("story_id") not in story_index
    ]
    question_files = [r["_file"] for r in question]
    blind_unknown_files = [r["_file"] for r in blind]

    return {
        "rows": rows,
        "orphan_reviews": sorted(orphan_reviews),
        "question_model_files": sorted(question_files),
        "blind_unknown_files_count": len(blind_unknown_files),
        "story_files": len(story_index),
        "analysis_files": len(analysis_index),
        "flash_review_files": len(flash),
        "blind_review_files": len(blind),
        "question_review_files": len(question),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Correlations
# ─────────────────────────────────────────────────────────────────────────────


def _story_outcomes(story_index: dict[str, dict], analysis_index: dict[str, dict]) -> dict[str, dict]:
    """Per-story outcome: all_successful + test-based success + condition + model.

    ``test_executed_success`` is the runtime test signal; for the story corpus the
    nearest measured proxies are the story's ``all_successful`` flag and the analysis
    ``deep.solution`` test pass ratio. Both are recorded so p2 can cite whichever is
    available.
    """
    outcomes: dict[str, dict] = {}
    for sid, story in story_index.items():
        analysis = analysis_index.get(sid, {})
        sol = (analysis.get("deep") or {}).get("solution") or {}
        tp = sol.get("tests_passed")
        tt = sol.get("tests_total")
        test_success = None
        if isinstance(tp, (int, float)) and isinstance(tt, (int, float)) and tt > 0:
            test_success = bool(tp >= tt)
        outcomes[sid] = {
            "model": story.get("model") or "unknown",
            "condition": story.get("perturbation_condition") or "clean",
            "all_successful": bool(story.get("summary", {}).get("all_successful")),
            "test_executed_success": test_success,
        }
    return outcomes


def _review_scores_per_story(flash: list[dict], blind: list[dict], question: list[dict]) -> dict[str, dict]:
    """Per-story mean review scores (architectural_fit, convention_adherence, debt, worse)."""
    per_story: dict[str, dict] = defaultdict(
        lambda: {"architectural_fit": [], "convention_adherence": [], "debt": 0,
                 "n": 0, "worse": 0, "wrong_approach": 0, "problems": 0}
    )
    for review in flash + blind + question:
        sid = review.get("story_id")
        if not sid:
            continue
        row = per_story[sid]
        for cr in review.get("commit_reviews", []) or []:
            row["n"] += 1
            af = cr.get("architectural_fit")
            ca = cr.get("convention_adherence")
            if isinstance(af, (int, float)):
                row["architectural_fit"].append(float(af))
            if isinstance(ca, (int, float)):
                row["convention_adherence"].append(float(ca))
            if cr.get("introduces_technical_debt"):
                row["debt"] += 1
            if cr.get("better_or_worse") == "worse":
                row["worse"] += 1
            themes: set[str] = set()
            for problem in cr.get("problems", []) or []:
                row["problems"] += 1
                themes |= _match_themes(_problem_text(problem))
            if "wrong-approach" in themes:
                row["wrong_approach"] += 1
    # roll up
    out: dict[str, dict] = {}
    for sid, row in per_story.items():
        n = row["n"]
        af = row["architectural_fit"]
        ca = row["convention_adherence"]
        out[sid] = {
            "n_commit_reviews": n,
            "mean_architectural_fit": round(float(np.mean(af)), 4) if af else None,
            "mean_convention_adherence": round(float(np.mean(ca)), 4) if ca else None,
            "debt_rate": round(row["debt"] / n, 4) if n else None,
            "worse_rate": round(row["worse"] / n, 4) if n else None,
            "wrong_approach_rate": round(row["wrong_approach"] / n, 4) if n else None,
        }
    return out


def _pearson(xs: list[float], ys: list[float]) -> dict | None:
    """Pearson correlation + p-value; ``None`` when scipy is unavailable or n < 3."""
    if stats is None or len(xs) < 3 or len(xs) != len(ys):
        return None
    r, p = stats.pearsonr(xs, ys)
    return {"r": round(float(r), 4), "p": round(float(p), 6), "n": len(xs)}


def _point_biserial(xs: list[float], ys: list[bool]) -> dict | None:
    """Point-biserial correlation between a continuous score and a binary outcome."""
    if stats is None or len(xs) < 3 or len(xs) != len(ys):
        return None
    r, p = stats.pointbiserialr(xs, ys)
    return {"r": round(float(r), 4), "p": round(float(p), 6), "n": len(xs)}


def _derive_correlations(
    flash: list[dict], blind: list[dict], question: list[dict],
    story_index: dict[str, dict], analysis_index: dict[str, dict],
) -> dict:
    """Compute the computable correlations (spec item 3)."""
    outcomes = _story_outcomes(story_index, analysis_index)
    scores = _review_scores_per_story(flash, blind, question)

    # (a) review scores vs story outcomes (all_successful + test_executed_success).
    score_vs_success: dict[str, dict] = {}
    for score_name in ("mean_architectural_fit", "mean_convention_adherence"):
        xs: list[float] = []
        ys_all: list[bool] = []
        ys_test: list[bool] = []
        for sid, row in scores.items():
            val = row.get(score_name)
            outcome = outcomes.get(sid)
            if val is None or outcome is None:
                continue
            xs.append(val)
            ys_all.append(outcome["all_successful"])
            if outcome["test_executed_success"] is not None:
                ys_test.append(outcome["test_executed_success"])
        # point-biserial for all_successful; point-biserial over the test-success subset
        # (a list of (sid, score) pairs -> score list + boolean outcome list).
        xs_test, ys_test = _zip_scores_test(scores, outcomes, score_name)
        score_vs_success[score_name] = {
            "vs_all_successful": _point_biserial(xs, ys_all),
            "vs_test_executed_success": _point_biserial(xs_test, ys_test),
        }

    # (b) debt rate vs condition, (c) wrong-approach rate vs condition — over the whole
    # flash-reviewed corpus (the reviewer is flash; condition is the subject story's).
    by_condition: dict[str, dict] = defaultdict(
        lambda: {"n_stories": 0, "n_commit_reviews": 0, "debt": 0, "wrong_approach": 0}
    )
    for sid, row in scores.items():
        outcome = outcomes.get(sid)
        if outcome is None:
            continue
        bucket = by_condition[outcome["condition"]]
        bucket["n_stories"] += 1
        bucket["n_commit_reviews"] += row["n_commit_reviews"]
        bucket["debt"] += round(row["debt_rate"] * row["n_commit_reviews"])
        bucket["wrong_approach"] += round(row["wrong_approach_rate"] * row["n_commit_reviews"])

    condition_rates = {}
    for cond, bucket in sorted(by_condition.items()):
        n = bucket["n_commit_reviews"]
        condition_rates[cond] = {
            "n_stories": bucket["n_stories"],
            "n_commit_reviews": n,
            "debt_rate": round(bucket["debt"] / n, 4) if n else None,
            "wrong_approach_rate": round(bucket["wrong_approach"] / n, 4) if n else None,
        }

    # per-subject-model debt/wrong-approach rate by condition (flash reviewer).
    per_model_condition: dict[str, dict] = defaultdict(
        lambda: defaultdict(lambda: {"n": 0, "debt": 0, "wrong_approach": 0})
    )
    for sid, row in scores.items():
        outcome = outcomes.get(sid)
        if outcome is None:
            continue
        bucket = per_model_condition[outcome["model"]][outcome["condition"]]
        bucket["n"] += row["n_commit_reviews"]
        bucket["debt"] += round(row["debt_rate"] * row["n_commit_reviews"])
        bucket["wrong_approach"] += round(row["wrong_approach_rate"] * row["n_commit_reviews"])
    per_model_condition_out = {
        model: {
            cond: {
                "n": b["n"],
                "debt_rate": round(b["debt"] / b["n"], 4) if b["n"] else None,
                "wrong_approach_rate": round(b["wrong_approach"] / b["n"], 4) if b["n"] else None,
            }
            for cond, b in conds.items()
        }
        for model, conds in per_model_condition.items()
    }

    return {
        "score_vs_outcome": score_vs_success,
        "condition_rates": condition_rates,
        "per_model_condition_rates": per_model_condition_out,
    }


def _zip_scores_test(scores, outcomes, score_name):
    """Yield ``(xs, ys)`` for stories that have both a score and a test outcome."""
    xs: list[float] = []
    ys: list[bool] = []
    for sid, row in scores.items():
        val = row.get(score_name)
        outcome = outcomes.get(sid)
        if val is None or outcome is None or outcome["test_executed_success"] is None:
            continue
        xs.append(val)
        ys.append(outcome["test_executed_success"])
    return xs, ys


# ─────────────────────────────────────────────────────────────────────────────
# Output + LOG
# ─────────────────────────────────────────────────────────────────────────────


def _coverage_csv(coverage: dict, path: Path) -> None:
    rows = [
        ["model", "stories", "analyzed", "reviewed", "uncovered"],
    ]
    for model in CANONICAL_MODELS:
        r = coverage["rows"].get(model, {})
        rows.append([
            model, r.get("stories", 0), r.get("analyzed", 0),
            r.get("reviewed", 0), len(r.get("uncovered", [])),
        ])
    # any non-canonical subject model present in the story corpus (should be none).
    for model in sorted(coverage["rows"]):
        if model not in CANONICAL_MODELS:
            r = coverage["rows"][model]
            rows.append([model, r["stories"], r["analyzed"], r["reviewed"], len(r["uncovered"])])
    path.write_text("\n".join(",".join(map(str, row)) for row in rows) + "\n", encoding="utf-8")


def _profiles_csv(rollups: dict, path: Path) -> None:
    header = [
        "model", "review_files", "commit_reviews", "mean_architectural_fit",
        "mean_convention_adherence", "debt_rate", "better", "neutral", "worse", "unclear",
    ]
    lines = [",".join(header)]
    for model in CANONICAL_MODELS:
        r = rollups.get(model)
        if r is None:
            continue
        bw = r["better_or_worse"]
        lines.append(",".join([
            model, str(r["review_files"]), str(r["commit_reviews"]),
            str(r["mean_architectural_fit"]), str(r["mean_convention_adherence"]),
            str(r["debt_rate"]), str(bw.get("better", 0)), str(bw.get("neutral", 0)),
            str(bw.get("worse", 0)), str(bw.get("unclear", 0)),
        ]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _log(models: list[str], rollups: dict, coverage: dict) -> str:
    """Render the LOG: per-model table + coverage table (spec deliverable)."""
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("PER-MODEL QUALITATIVE PROFILE (subject model; reviewer = flash)")
    lines.append("=" * 78)
    lines.append(
        f"{'model':36s} {'files':>5s} {'commits':>7s} {'archfit':>7s} "
        f"{'conven':>6s} {'debt':>6s} {'better':>6s} {'worse':>5s}"
    )
    for model in models:
        r = rollups.get(model)
        if r is None:
            continue
        bw = r["better_or_worse"]
        lines.append(
            f"{model:36s} {r['review_files']:>5d} {r['commit_reviews']:>7d} "
            f"{_f(r['mean_architectural_fit']):>7s} {_f(r['mean_convention_adherence']):>6s} "
            f"{_f(r['debt_rate']):>6s} {bw.get('better', 0):>6d} {bw.get('worse', 0):>5d}"
        )
    lines.append("")
    lines.append("=" * 78)
    lines.append("COVERAGE TABLE")
    lines.append("=" * 78)
    lines.append(f"{'model':36s} {'stories':>7s} {'analyzed':>8s} {'reviewed':>8s} {'uncovered':>9s}")
    for model in models:
        r = coverage["rows"].get(model, {})
        lines.append(
            f"{model:36s} {r.get('stories', 0):>7d} {r.get('analyzed', 0):>8d} "
            f"{r.get('reviewed', 0):>8d} {len(r.get('uncovered', [])):>9d}"
        )
    lines.append("")
    lines.append("=" * 78)
    lines.append("DISCLOSED THEME PATTERNS (methodology, hard rule 3)")
    lines.append("=" * 78)
    for theme, patterns in THEME_PATTERNS.items():
        lines.append(f"  {theme:18s} {patterns}")
    lines.append("")
    lines.append(f"story files: {coverage['story_files']} | analysis files: "
                 f"{coverage['analysis_files']} | flash review files: {coverage['flash_review_files']} "
                 f"| blind review files: {coverage['blind_review_files']} "
                 f"| '?'-model files: {coverage['question_review_files']}")
    lines.append(f"orphan reviews (story file absent): {len(coverage['orphan_reviews'])}")
    if coverage["question_model_files"]:
        lines.append("'?'-model files: " + ", ".join(coverage["question_model_files"]))
    return "\n".join(lines)


def _f(value) -> str:
    """Format a float/None to a fixed-width string."""
    return "—" if value is None else f"{value:.3f}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute the per-model qualitative profiles.")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR,
                        help="Output directory (default: experiments/results/qualitative_routing/)")
    parser.add_argument("--dry-run", action="store_true", help="Print LOG, write nothing")
    args = parser.parse_args()

    story_index = _load_story_index()
    analysis_index = _load_analysis_index()
    flash, blind, question = _load_reviews()

    profiles = _derive_profiles(flash, blind, question, story_index)
    rollups = {m: _rollup_profile(profiles[m]) for m in profiles if profiles[m]["commit_reviews"]}
    summaries = {m: _top_summaries(profiles[m]) for m in profiles}
    coverage = _derive_coverage(story_index, analysis_index, flash, blind, question)
    correlations = _derive_correlations(flash, blind, question, story_index, analysis_index)

    result = {
        "workflow": "qualitative_routing_analysis",
        "phase": "p1_compute",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus": {
            "story_files": coverage["story_files"],
            "analysis_files": coverage["analysis_files"],
            "flash_review_files": coverage["flash_review_files"],
            "blind_review_files": coverage["blind_review_files"],
            "question_model_files": coverage["question_model_files"],
            "orphan_reviews": coverage["orphan_reviews"],
            "total_commit_reviews": sum(r["commit_reviews"] for r in rollups.values()),
        },
        "methodology": {
            "subject_model_join": (
                "review.story_id -> story.model; the review file's 'model' field is the "
                "REVIEWER (always deepseek/deepseek-v4-flash), not the subject."
            ),
            "theme_patterns": THEME_PATTERNS,
            "theme_pattern_limits": [
                "keyword substring matching — false positives/negatives possible; heuristic, not taxonomy.",
                "a problem may match multiple themes; per-theme rates are non-exclusive.",
                "blind reviews' problems are plain strings (no category/severity); flash reviews' are dicts.",
            ],
        },
        "profiles": rollups,
        "top_summaries": summaries,
        "coverage": coverage,
        "correlations": correlations,
    }

    log = _log(CANONICAL_MODELS, rollups, coverage)
    print(log)

    if args.dry_run:
        print("\n[dry-run] nothing written")
        return 0

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "qualitative_routing_compute.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8")
    _coverage_csv(coverage, args.out_dir / "coverage_table.csv")
    _profiles_csv(rollups, args.out_dir / "per_model_profiles.csv")
    print(f"\nWrote: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
