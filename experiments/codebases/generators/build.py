"""
Codebase catalog generator — Flash V4 degradation of good seams.

Takes a "good seams" codebase and produces a "bad seams" variant by
introducing deliberate architectural degradation through Flash V4.
"""

import json
from pathlib import Path

from instrument.mutation import (
    compile_mutation,
    apply_mutation,
    MutationArtifact,
)


CATALOG_ROOT = Path(__file__).resolve().parent.parent


def generate_bad_variant(language: str, tier: str) -> list[MutationArtifact]:
    """Generate all bad-seams variants for a language + tier.

    Returns list of mutation artifacts (one per degrading operator applied).
    """
    good_path = CATALOG_ROOT / language / tier / "good"
    bad_path = CATALOG_ROOT / language / tier / "bad"

    if not good_path.exists():
        raise FileNotFoundError(f"Good codebase not found: {good_path}")

    artifacts: list[MutationArtifact] = []
    degraders = [
        "introduce_coupling",
        "duplicate_abstraction",
        "break_convention",
    ]

    for operator in degraders:
        artifact = compile_mutation(
            specification=f"Degrade the {language} codebase.",
            operator=operator,
            strength=0.5,
            codebase_path=good_path,
        )
        if artifact.codebase_patch:
            artifact.save(bad_path / f"{artifact.mutation_id}.json")
            artifacts.append(artifact)
            print(f"  Generated: {artifact.mutation_id} ({operator})")
        else:
            print(f"  Skipped: {operator} (no patch generated)")

    return artifacts


def apply_all_bad_variants(language: str, tier: str) -> None:
    """Apply all generated bad-seams patches to build the bad variant."""
    import shutil
    import subprocess

    good_path = CATALOG_ROOT / language / tier / "good"
    bad_path = CATALOG_ROOT / language / tier / "bad"

    # Reset bad directory from good
    if bad_path.exists():
        shutil.rmtree(bad_path)
    shutil.copytree(good_path, bad_path)

    # Apply all patches
    for patch_file in sorted(bad_path.glob("*.json")):
        artifact = MutationArtifact.load(patch_file)
        print(f"  Applying: {artifact.mutation_id} ({artifact.operator})")
        apply_mutation(artifact, bad_path)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate codebase catalog variants.")
    parser.add_argument("language", help="Language (python, typescript, go, rust)")
    parser.add_argument("--tier", default="tier1_minimal", help="Codebase tier")
    parser.add_argument("--apply", action="store_true", help="Apply patches to build bad variant")

    args = parser.parse_args()

    if args.apply:
        apply_all_bad_variants(args.language, args.tier)
    else:
        generate_bad_variant(args.language, args.tier)


if __name__ == "__main__":
    main()
