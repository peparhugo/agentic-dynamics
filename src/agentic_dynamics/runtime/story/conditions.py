"""Perturbation conditions — the experimental condition model + mutation mapping.

Extracted from ``runtime/story.py`` (refactor-repair Debt-1). ``condition_to_mutations`` maps a
``PerturbationCondition`` to concrete mutations. ``compile_mutation`` is imported lazily inside
``condition_to_mutations`` so the story test suite can monkeypatch ``story.compile_mutation``.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path

from agentic_dynamics.measurement.mutation import MutationArtifact


class PerturbationCondition(str, Enum):
    """Experimental conditions for perturbing multi-session stories."""

    CLEAN = "clean"  # No mutation, no codebase degradation
    BAD_SEED = "bad_seed"  # Codebase degraded before session 1
    EARLY_DEGRADE = "early_degrade"  # Session 1 spec corrupted only
    LATE_DEGRADE = "late_degrade"  # Session 4 spec corrupted only (v1.5)


# Canonical mutation strength for the degrading conditions (BAD_SEED / EARLY_DEGRADE /
# LATE_DEGRADE). The strength axis is a first-class ledger field: CLEAN maps to
# s = 0.0 (the unperturbed baseline) and every degrading condition to this value,
# so a story result carries a numeric ``perturbation_strength``, not just the
# categorical ``perturbation_condition`` string.
CONDITION_STRENGTH = 0.5


def condition_to_mutations(
    condition: PerturbationCondition,
    codebase_path: Path,
    story_specs: list[str],
    *,
    compiler_model: str = "deepseek/deepseek-v4-flash",
    cache_dir: Path | None = None,
) -> tuple[MutationArtifact | None, dict[int, MutationArtifact]]:
    """Map a perturbation condition to specific mutations.

    For BAD_SEED: looks for a pre-generated 'bad/' variant at the same
    directory level. If found, returns a no-op artifact (the codebase
    is pre-degraded on disk). If not found, returns None (skip BAD_SEED).

    For EARLY_DEGRADE / LATE_DEGRADE: compiles spec mutations via Flash V4
    at runtime (these are cheap, single-prompt calls).

    Args:
        condition: Experimental condition.
        codebase_path: Path to seed codebase.
        story_specs: Session prompts in order.
        compiler_model: Model for mutation compilation.
        cache_dir: Optional cache directory.

    Returns:
        (codebase_mutation, {session_number: spec_mutation})
    """
    # Late import: resolve through the package so tests can monkeypatch
    # ``story.compile_mutation`` (measurement.mutation is the default).
    from agentic_dynamics.runtime.story import compile_mutation  # noqa: F401
    cache = cache_dir or Path("experiments/codebases/.mutation_cache")
    cache.mkdir(parents=True, exist_ok=True)

    if condition == PerturbationCondition.CLEAN:
        return None, {}

    if condition == PerturbationCondition.BAD_SEED:
        # Look for pre-generated bad variant on disk
        # e.g. ".../tier1_minimal/good" -> ".../tier1_minimal/bad"
        bad_path = codebase_path.parent / "bad"
        if bad_path.exists() and any(bad_path.iterdir()):
            return MutationArtifact(
                mutation_id="bad_seed_pregen",
                operator="bad_seed",
                operator_class="codebase",
                strength=CONDITION_STRENGTH,
                original_spec="Pre-generated bad variant",
                codebase_patch=f"Using pre-generated variant at {bad_path}",
            ), {}
        return None, {}

    if condition == PerturbationCondition.EARLY_DEGRADE:
        if not story_specs:
            return None, {}
        artifact = compile_mutation(
            specification=story_specs[0],
            operator="inject_false_premise",
            strength=CONDITION_STRENGTH,
            model=compiler_model,
            cache_dir=cache,
        )
        return None, {1: artifact}

    if condition == PerturbationCondition.LATE_DEGRADE:
        if len(story_specs) < 4:
            return None, {}
        artifact = compile_mutation(
            specification=story_specs[3],
            operator="remove_constraint",
            strength=CONDITION_STRENGTH,
            model=compiler_model,
            cache_dir=cache,
        )
        return None, {4: artifact}

    return None, {}

