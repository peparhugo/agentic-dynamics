"""The singular publication door (canonical-publication closure, phase c1).

``docs/reviews/canonical_publication_review.md`` P0:

    The lab path is canonical, but the primary story/model/review/analysis sections still
    flow through ``stories/*.json -> sync_data -> parquet`` and raw ``reviews/*.json`` /
    ``analysis/*.json`` globs. ``data.js`` carries ``bad_seed 41 / early_degrade 91``
    against the canonical ``clean 135 / early_degrade 72``.

This module makes the correction permanent rather than a one-time fix:

1. **One door** — the public-data producers (``build_data.py``, ``sync_data.py``) resolve
   their input through ``canonical_corpus.load_canonical_tables`` and never build their own
   path into ``experiments/results/{stories,reviews,analysis}`` (AST-checked, string
   literals only, docstrings exempt).
2. **The relabel is absolute** — the canonical condition split is exactly
   ``clean 135 / early_degrade 72``: no ``bad_seed`` arm, no ``early_degrade 91``, no
   empty label. The no-op ``bad_seed``/``early_degrade`` cells (and absent labels) ARE
   ``clean`` (``docs/data_integrity_findings.md`` treatment rule 1).
3. **``data.js`` agrees** — the published ``stories.conditions`` block carries the same
   split, so the site can never re-report the legacy ``bad_seed 41`` semantics.
"""

from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path

import pytest

from agentic_dynamics.reporting import canonical_corpus as cc

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
DATA_JS = ROOT / "apps" / "website" / "data.js"

#: The public-data producers that feed ``data.js`` (and the parquet it used to read).
#: These are the non-lab "publishers" the review's P0 named as bypassing the resolver.
PUBLIC_DATA_PRODUCERS = ("build_data.py", "sync_data.py")

#: Result directories a public-data producer may not walk on its own. Reading these by
#: glob (outside the resolver) is what "the raw parquet/glob path" means in the review.
FORBIDDEN_GLOB_ROOTS = (
    "experiments/results/stories",
    "experiments/results/reviews",
    "experiments/results/analysis",
)

#: The canonical condition split (docs/reviews/canonical_publication_review.md P0).
#: 225 current story rows − 10 payload-less = 215 resolved; 135 clean (incl. the 9
#: empty-label + relabeled no-ops) and 72 genuinely instrumented ``early_degrade``.
CANONICAL_SPLIT = {"clean": 135, "early_degrade": 72}


def _docstring_ids(tree: ast.AST) -> set[int]:
    """``id()`` of every docstring Constant (so prose can discuss what code may not do)."""
    out: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and body
        ):
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                out.add(id(first.value))
    return out


# ---------------------------------------------------------------------------
# 1. One door — no producer walks a raw result directory on its own
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("script", PUBLIC_DATA_PRODUCERS)
def test_public_data_producer_uses_the_canonical_resolver(script: str):
    """Every public-data producer resolves input through ``load_canonical_tables``."""
    src = (SCRIPTS_DIR / script).read_text(encoding="utf-8")
    assert "load_canonical_tables" in src, (
        f"{script} must resolve its input through canonical_corpus.load_canonical_tables"
    )


@pytest.mark.parametrize("script", PUBLIC_DATA_PRODUCERS)
def test_public_data_producer_does_not_glob_raw_result_dirs(script: str):
    """No producer may construct its own path into the raw result directories.

    AST-based (string literals only, docstrings excluded) so the prose explaining the
    rule does not trip it. ``build_data.py`` names the four tables verbatim in its
    ``load_canonical_tables("story", "finding", "review", "analysis")`` call — those are
    table *names*, not result-directory paths, so they are not flagged.
    """
    tree = ast.parse((SCRIPTS_DIR / script).read_text(encoding="utf-8"), filename=script)
    docstrings = _docstring_ids(tree)

    offenders = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
        and any(root in node.value for root in FORBIDDEN_GLOB_ROOTS)
    ]
    assert not offenders, (
        f"{script} builds its own path into a raw result directory {offenders} — "
        f"public-data producers must resolve inputs through the registry"
    )


# ---------------------------------------------------------------------------
# 2 + 3. The relabel is absolute, and data.js agrees
# ---------------------------------------------------------------------------


def test_canonical_condition_split_has_no_bad_seed_arm():
    """The resolver's canonical split is exactly ``clean 135 / early_degrade 72``."""
    identity = cc.current_manifest_identity()
    if not identity.registry_identity_sha256:  # pragma: no cover - manifest present in CI
        pytest.skip("no data_manifest.json registry in this checkout")

    tables = cc.load_canonical_tables("story")
    counts = Counter(s.get("_canonical_condition") for s in tables.stories)

    # No bad_seed, no early_degrade 91, no empty label — every cell is a real condition.
    assert set(counts) == set(CANONICAL_SPLIT), (
        f"canonical conditions {dict(counts)} must be exactly clean/early_degrade "
        f"(the no-op relabel removes bad_seed and empty labels)"
    )
    assert dict(counts) == CANONICAL_SPLIT, (
        f"canonical split drifted: {dict(counts)} != {CANONICAL_SPLIT}"
    )


def test_data_js_story_conditions_match_the_canonical_split():
    """The published ``data.js`` condition block agrees with the resolver — exactly once.

    The contradiction the review found — ``data.js`` reporting ``bad_seed 41`` /
    ``early_degrade 91`` alongside the canonical ``clean 135 / early_degrade 72`` — is
    closed only if the published block is *exactly* the canonical split: two arms, each
    appearing once, with no ``bad_seed``/``early_degrade-91`` arm surviving.
    """
    if not DATA_JS.exists():  # pragma: no cover - generated file, present in CI
        pytest.skip("apps/website/data.js not generated")
    text = DATA_JS.read_text(encoding="utf-8")
    payload = json.loads(text[text.index("{") : text.rindex("}") + 1])

    arms = [(c["condition"], c["cells"]) for c in payload["stories"]["conditions"]]
    counts = Counter(arms)
    assert counts == {("clean", 135): 1, ("early_degrade", 72): 1}, (
        f"data.js stories.conditions {dict(counts)} != the canonical split exactly once "
        f"(clean 135 / early_degrade 72) — a duplicate or a legacy arm is present"
    )
    # Explicitly: no bad_seed-41 arm, no early_degrade-91 arm.
    assert ("bad_seed", 41) not in counts
    assert ("early_degrade", 91) not in counts


def _data_js_payload() -> dict | None:
    """Parse ``window.DYNAMICS_DATA`` out of the generated ``data.js``."""
    if not DATA_JS.exists():  # pragma: no cover - generated file, present in CI
        return None
    text = DATA_JS.read_text(encoding="utf-8")
    return json.loads(text[text.index("{") : text.rindex("}") + 1])


def test_readme_figures_match_public_statistics():
    """Every README "By the Numbers" figure mirrors ``public_statistics`` — wholesale.

    The review's "smaller" issue: the guard checked only three corrected figures while the
    README table also displayed a provider count, spec counts, and a lab split that were not
    in ``public_statistics``. The block is now reconstructed line-by-line from the canonical
    block, so any figure — present or future — that drifts fails here, and the stale figures
    must not survive anywhere.
    """
    payload = _data_js_payload()
    if payload is None:  # pragma: no cover
        pytest.skip("apps/website/data.js not generated")
    ps = payload.get("public_statistics", {})
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    # Reconstruct each table row exactly as the README renders it. A new headline figure
    # added to the table without a matching public_statistics key (or vice-versa) is a drift.
    expected_lines = [
        f"| Story sessions | {ps['story_sessions']:,} ({ps['db_sessions_total']:,} DB sessions total) |",
        f"| Game reports | {ps['game_reports']} |",
        f"| Model variants | {ps['model_variants']} ({ps['providers']} providers: DeepSeek, Anthropic, OpenAI) |",
        f"| Experiment configs | {ps['experiment_configs']} |",
        f"| Experiment + workflow specs | {ps['experiment_specs'] + ps['workflow_specs']} "
        f"({ps['experiment_specs']} experiments + {ps['workflow_specs']} workflows) |",
        f"| Perturbation operators | {ps['perturbation_operators']} "
        "(specification corruption, objective mutation, process perturbation) |",
        f"| Lab books | {ps['lab_books']} ({ps['lab_books_canonical']} canonical + "
        f"{ps['lab_books_quarantined']} quarantined) |",
        f"| Story-corpus measured spend | ${ps['measured_spend_usd']:,.2f} |",
    ]
    for line in expected_lines:
        assert line in readme, f"README 'By the Numbers' drifted: {line!r}"

    # The stale figures must not survive anywhere.
    for stale in ("1,097 story sessions", "$288.69", "36 (33 measurement + 3 grid/sweep)"):
        assert stale not in readme, f"stale figure returned: {stale}"
