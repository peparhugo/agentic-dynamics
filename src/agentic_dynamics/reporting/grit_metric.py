"""The ONE Grit metric definition (semantic-integrity release, phase s4 + step-6 extraction).

``G(s) = P(test_executed_success | perturbation_strength = s)`` — the formal metric the
README and the site glossary publish. After s4 there is exactly one Grit; after step 6 there
is exactly one *implementation* of it: ``scripts/lab_grit.py`` (the publication-eligible lab)
and ``control.projections.quality`` (the Control Room's P3 read model) BOTH compute from this
module, so a second meaning cannot re-enter through a second reader.

Why this module lives in ``reporting``: the metric is research output (tier 1), and the
projection layer (tier 2) may read tier-0/1 planes. A lab importing a control module would
invert the dependency direction; this module keeps the definition where the labs already are.

The rules encoded here (all of them were hard-won findings, not style):

* ``wilson_interval`` is deterministic (no bootstrap RNG — the lab's output must be
  byte-identical across runs) and correct at the extremes (a normal approximation around
  p=1.0 would extend above 1).
* ``rate_row`` reports a proportion ONLY with at least ``MIN_CELLS_FOR_RATE`` cells;
  below that ``grit`` is ``None`` with ``insufficient_support=True`` — an under-powered
  proportion is not a measurement.
* ``collect_cells`` excludes a cell missing ``perturbation_strength`` or
  ``test_executed_success`` outright (one canonical reason, ``missing_required_field``) —
  it is never imputed to 0.0 / False. It also captures the answer/explanation token split
  when present, so the narration dimension costs no second corpus pass.
"""

from __future__ import annotations

import math
from collections import Counter

from agentic_dynamics.reporting.lab_contract import record_id

#: The metric definition, carried in outputs so a reader never has to look it up — and so a
#: guard test can assert the README, the website and the lab state the same thing.
METRIC_DEFINITION = "G(s) = P(test_executed_success | perturbation_strength = s)"

#: Minimum cells before a breakdown row is reported as a rate. Below this a proportion is
#: noise; the row is still emitted (with ``grit: null``) so the gap is visible rather than
#: silently dropped.
MIN_CELLS_FOR_RATE = 5


def short_model(model: str) -> str:
    """``deepseek/deepseek-v4-flash`` -> ``deepseek-v4-flash`` (the report vocabulary)."""
    return model.split("/")[-1]


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion.

    Chosen over a bootstrap for two reasons: it is **deterministic** (the lab must produce
    byte-identical output across runs — see the s3 determinism check), and it behaves
    correctly at the extremes, where several of these cells sit (a normal-approximation
    interval around p=1.0 would extend above 1).
    """
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
    return (round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4))


def rate_row(label_key: str, label: str | float, successes: int, n: int, **extra) -> dict:
    """One reported proportion, with its interval and an explicit small-sample marker."""
    lo, hi = wilson_interval(successes, n)
    sufficient = n >= MIN_CELLS_FOR_RATE
    return {
        label_key: label,
        "n": n,
        "successes": successes,
        # None below the threshold: an under-powered proportion is not a measurement.
        "grit": round(successes / n, 4) if (n and sufficient) else None,
        "ci95_lo": lo if sufficient else None,
        "ci95_hi": hi if sufficient else None,
        "insufficient_support": not sufficient,
        **extra,
    }


def _exclusion_reason(has_strength: bool, has_verdict: bool) -> str:
    """The canonical reason a cell was excluded from the metric.

    Both ``perturbation_strength`` and ``test_executed_success`` are required; missing
    either (or both) is one canonical reason — ``missing_required_field`` — the
    public-truth review's P1 vocabulary. The finer strength-vs-verdict split was
    informational only and is folded here so the contract uses exactly the named reasons.
    """
    return "missing_required_field"


def _story_token_totals(story: dict) -> tuple[int | None, int | None]:
    """SUM the answer/explanation token split over a story's sessions, when captured.

    Story payloads nest the per-session agentic metrics; the split may sit on the session
    dict or inside ``agentic``. Returns ``(None, None)`` when no session captured them —
    an absent split is unknown, never zero.
    """
    answer: int | None = None
    explanation: int | None = None
    for session in story.get("sessions") or []:
        if not isinstance(session, dict):
            continue
        agentic = session.get("agentic") or {}
        for source in (agentic, session):
            av = source.get("answer_tokens")
            ev = source.get("explanation_tokens")
            if isinstance(av, int):
                answer = (answer or 0) + av
            if isinstance(ev, int):
                explanation = (explanation or 0) + ev
            if isinstance(av, int) or isinstance(ev, int):
                break
    return answer, explanation


def collect_cells(
    findings: list[dict], stories: list[dict]
) -> tuple[list[dict], dict[str, int], list[str], list[str]]:
    """Every canonical cell carrying BOTH fields the metric needs, plus the exclusion tally.

    A cell missing either field is excluded outright — the metric is a conditional
    probability, and a cell with no strength or no executed verdict cannot condition on
    anything. It is never imputed to 0.0 / False. The returned ``exclusions`` maps each
    reason to its count, so a contract can report *why* cells dropped out (review P2:
    ``n_resolved`` vs ``n_eligible`` vs ``n_excluded``). The returned ``used_refs`` /
    ``excluded_refs`` are the table-qualified record refs of the cells that DID / did NOT
    contribute (m3 ContributionReport; f2 exact contributor attestation).

    Each cell carries the narration split when the corpus captured it
    (``answer_tokens``/``explanation_tokens``, summed over story sessions) — ``None``
    when not captured.
    """
    cells: list[dict] = []
    exclusions: Counter = Counter()
    used_refs: list[str] = []
    excluded_refs: list[str] = []

    for run in findings:
        strength = run.get("perturbation_strength")
        verdict = run.get("test_executed_success")
        if not isinstance(strength, (int, float)) or not isinstance(verdict, bool):
            exclusions[
                _exclusion_reason(isinstance(strength, (int, float)), isinstance(verdict, bool))
            ] += 1
            excluded_refs.append(record_id(run))
            continue
        used_refs.append(record_id(run))
        answer = run.get("answer_tokens")
        explanation = run.get("explanation_tokens")
        cells.append(
            {
                "source": "finding",
                "strength": float(strength),
                "success": verdict,
                "model": short_model(str(run.get("model") or "unknown")),
                "perturbation_class": run.get("perturbation_class") or "unknown",
                "operator": run.get("operator") or "unknown",
                "answer_tokens": answer if isinstance(answer, int) else None,
                "explanation_tokens": explanation if isinstance(explanation, int) else None,
            }
        )

    for story in stories:
        strength = story.get("perturbation_strength")
        verdict = story.get("test_executed_success")
        if not isinstance(strength, (int, float)) or not isinstance(verdict, bool):
            exclusions[
                _exclusion_reason(isinstance(strength, (int, float)), isinstance(verdict, bool))
            ] += 1
            excluded_refs.append(record_id(story))
            continue
        used_refs.append(record_id(story))
        answer, explanation = _story_token_totals(story)
        cells.append(
            {
                "source": "story",
                "strength": float(strength),
                "success": verdict,
                "model": short_model(str(story.get("model") or "unknown")),
                # Stories carry a condition, not an operator class; label it as such rather
                # than forcing it into the finding corpus's vocabulary.
                "perturbation_class": f"story:{story.get('_canonical_condition') or 'clean'}",
                "operator": "story_condition",
                "answer_tokens": answer,
                "explanation_tokens": explanation,
            }
        )

    return cells, dict(exclusions), used_refs, excluded_refs
