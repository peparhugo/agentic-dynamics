"""Flash-authored prompt perturbation — the session path of the "starting point".

Companion to the deterministic operators in :mod:`instrument.perturb`. Where
``perturb_prompt`` applies a seeded, pure-function operator, this module hands the
perturbation to a cheap model (DeepSeek Flash V4) in a one-shot opencode session and
*pins the result* as a hashable, variant-indexed artifact. The two paths converge on the
same stored-asset contract: a perturbed prompt plus its sha256, reusable as a cell's
starting point regardless of which path produced it.

Deterministic draws are regenerable from ``derive_seed``; flash-authored perturbations are
NOT — they are stored once and reused from the cache/artifact, never recomputed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_dynamics.measurement.mutation import _call_opencode
from agentic_dynamics.measurement.perturb import build_operators, derive_seed, perturb_prompt

FLASH_MODEL = "deepseek/deepseek-v4-flash"

_PERTURBATION_TEMPLATE = """You are a perturbation compiler for an experimental measurement instrument.
Your job is to apply a specific reasoning-space perturbation to an engineering task prompt.

OPERATOR: {operator}
STRENGTH: {strength} (0.0 = minimal perturbation, 1.0 = maximum perturbation)
VARIANT: {variant} (a label distinguishing this perturbation from other variants of the same cell)

ORIGINAL PROMPT:
{prompt}

INSTRUCTIONS:
1. Apply the {operator} perturbation at strength {strength} to the prompt.
2. Produce a perturbation that reads as a coherent, natural task prompt — the goal is to
   shift the reasoning surface, not to obviously corrupt the task.
3. Make this VARIANT substantively distinct from other variants of the same cell.
4. Do NOT add commentary, explanations, or meta-commentary.
5. Output ONLY the perturbed prompt text.

PERTURBED PROMPT:"""


@dataclass
class PromptPerturbation:
    """A pinned, hashable perturbed-prompt artifact.

    ``id`` is a stable cache key derived from the *inputs* (operator, strength, variant,
    base prompt, model) so the same cell reuses the same artifact. ``sha256`` is the
    content hash of ``perturbed_prompt``, matching the ``perturbed_prompt_sha256`` field
    persisted by ``scripts/run.py``.
    """

    operator: str
    strength: float
    seed_variant: int
    base_prompt: str
    perturbed_prompt: str = ""
    model: str = FLASH_MODEL
    provenance: str = "flash"  # "flash" | "deterministic"
    compiled_at: str = ""
    id: str = ""
    sha256: str = ""

    def __post_init__(self) -> None:
        if not self.compiled_at:
            self.compiled_at = datetime.now(timezone.utc).isoformat()
        if self.perturbed_prompt and not self.sha256:
            self.sha256 = hashlib.sha256(self.perturbed_prompt.encode("utf-8")).hexdigest()
        if not self.id:
            self.id = self._make_id()

    def _make_id(self) -> str:
        base_digest = hashlib.sha256(self.base_prompt.encode("utf-8")).hexdigest()[:16]
        key = f"{self.operator}|{self.strength}|{self.seed_variant}|{self.model}|{base_digest}"
        return "pp_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PromptPerturbation":
        return cls(**d)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, s: str) -> "PromptPerturbation":
        return cls.from_dict(json.loads(s))

    def save(self, path: Path) -> None:
        path.write_text(self.to_json())

    @classmethod
    def load(cls, path: Path) -> "PromptPerturbation":
        return cls.from_json(path.read_text())


def compile_prompt_perturbation(
    base_prompt: str,
    operator: str,
    strength: float = 0.5,
    *,
    seed_variant: int = 0,
    model: str = FLASH_MODEL,
    cache_dir: Path | None = None,
    timeout: int = 300,
) -> PromptPerturbation:
    """Author a reasoning-space perturbation with a cheap model and pin it as an artifact.

    Mirrors :func:`instrument.mutation.compile_mutation`, but for the prompt itself: the
    ``(operator, strength, seed_variant, base_prompt, model)`` cell is sent to Flash in a
    one-shot session, and the returned perturbed prompt is stored (and cached) so every
    session consuming this cell sees the identical starting point.

    Args:
        base_prompt: Original clean task prompt.
        operator: One of the reasoning-space operators (``build_operators()``).
        strength: Perturbation strength 0.0–1.0.
        seed_variant: The starting-point index — distinct variants yield distinct prompts.
        model: Model that authors the perturbation (cheap — flash by default).
        cache_dir: Directory for cached artifacts (reuse instead of re-authoring).
        timeout: Seconds for the opencode session.

    Returns:
        A pinned :class:`PromptPerturbation`.

    Raises:
        ValueError: If the operator is unknown, strength is out of range, or the compiler
            model returns no output.
    """
    if operator not in build_operators():
        raise ValueError(f"Unknown operator: {operator!r}")
    if not 0.0 <= strength <= 1.0:
        raise ValueError(f"Strength must be 0.0–1.0, got {strength}")

    probe = PromptPerturbation(
        operator=operator,
        strength=strength,
        seed_variant=seed_variant,
        base_prompt=base_prompt,
        model=model,
    )
    cache_path = cache_dir / f"{probe.id}.json" if cache_dir else None
    if cache_path is not None and cache_path.exists():
        return PromptPerturbation.load(cache_path)

    prompt = _PERTURBATION_TEMPLATE.format(
        operator=operator,
        strength=strength,
        variant=seed_variant,
        prompt=base_prompt,
    )
    perturbed = _call_opencode(prompt, model=model, timeout=timeout)
    if not perturbed or not perturbed.strip():
        raise ValueError(
            f"prompt perturbation failed for operator {operator!r} variant "
            f"{seed_variant}: compiler model {model!r} returned no output"
        )

    probe.perturbed_prompt = perturbed.strip()
    probe.sha256 = hashlib.sha256(probe.perturbed_prompt.encode("utf-8")).hexdigest()
    probe.compiled_at = datetime.now(timezone.utc).isoformat()

    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        probe.save(cache_path)

    return probe


def resolve_perturbed_prompt(
    base_prompt: str,
    operator: str,
    strength: float = 0.5,
    *,
    seed_variant: int = 0,
    mode: str = "deterministic",
    model: str = FLASH_MODEL,
    cache_dir: Path | None = None,
    timeout: int = 300,
) -> tuple[str, str, str]:
    """Return ``(perturbed_prompt, sha256, provenance)`` for a cell's starting point.

    ``mode == "deterministic"`` (default) uses the seeded pure-function operators
    (:func:`instrument.perturb.perturb_prompt`) — fully regenerable, no model call.
    ``mode == "flash"`` authors the perturbation with a cheap model and pins it as an
    artifact (:func:`compile_prompt_perturbation`) — stored, not regenerable.
    """
    if mode == "flash":
        art = compile_prompt_perturbation(
            base_prompt, operator, strength,
            seed_variant=seed_variant, model=model, cache_dir=cache_dir, timeout=timeout,
        )
        return art.perturbed_prompt, art.sha256, "flash"

    seed = derive_seed(base_prompt, operator, strength, seed_variant)
    prompt, _ = perturb_prompt(base_prompt, operator, strength=strength, rng_seed=seed)
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return prompt, digest, "deterministic"
