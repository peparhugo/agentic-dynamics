"""Reasoning-space perturbation operators.

Unlike the old genotype mutation system (which changed *what* the model
was asked to build), these operators perturb the *reasoning context*
while holding the task constant. This lets us measure how reasoning
policies respond to being pushed off their typical manifold.

Each operator is a named function that takes a prompt context and
returns a perturbed version. Operators are pure functions with a
``strength`` parameter (0.0 = no perturbation, 1.0 = maximum).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable

# ── Alien vocabularies — cross-domain word sets for directional noise ──

ALIEN_VOCABULARIES: dict[str, list[str]] = {
    "biology": [
        "mycelial", "symbiosis", "metamorphosis", "homeostasis", "emergence",
        "entropy", "resonance", "catalyst", "membrane", "neural_dendrite",
        "pheromone", "ecosystem", "mutation", "adaptation", "photosynthesis",
        "mitochondria", "synapse", "fermentation", "metamorphic", "rhizome",
    ],
    "music": [
        "counterpoint", "syncopation", "resonance", "timbre", "crescendo",
        "arpeggio", "dissonance", "overtone", "polyrhythm", "leitmotif",
        "ostinato", "glissando", "staccato", "legato", "cadenza",
        "harmonics", "modulation", "diminuendo", "fugue", "improvisation",
    ],
    "architecture": [
        "cantilever", "parapet", "atrium", "fenestration", "colonnade",
        "buttress", "mezzanine", "cornice", "pilaster", "portico",
        "vestibule", "balustrade", "clerestory", "arcade", "pergola",
        "entablature", "pediment", "rotunda", "loggia", "brise_soleil",
    ],
    "cooking": [
        "braise", "emulsify", "deglaze", "caramelize", "confit",
        "julienne", "macerate", "blanch", "flambe", "proof",
        "render", "temper", "zest", "infuse", "reduction",
        "mise_en_place", "sous_vide", "brunoise", "veloute", "beurre_noisette",
    ],
    "warfare": [
        "flanking", "pincer", "envelopment", "vanguard", "rearguard",
        "salient", "defilade", "interdiction", "exfiltration", "overwatch",
        "reconnaissance", "feint", "diversion", "counteroffensive", "logistics",
        "bivouac", "skirmish", "sortie", "salvo", "barrage",
    ],
    "oceanography": [
        "bathypelagic", "thermocline", "upwelling", "abyssal", "littoral",
        "pelagic", "benthic", "estuarine", "halocline", "gyre",
        "nekton", "planktonic", "bathymetry", "fetch", "swell",
        "rip_current", "longshore", "seiche", "tsunami", "eddy",
    ],
    "astronomy": [
        "parallax", "redshift", "singularity", "nebula", "quasar",
        "pulsar", "event_horizon", "accretion", "supernova", "dark_matter",
        "exoplanet", "cosmic_microwave", "gravitational_lens", "heliopause", "magnetosphere",
        "synchrotron", "coronal_mass", "transit", "occultation", "zenith",
    ],
    "theater": [
        "denouement", "soliloquy", "mise_en_scene", "verfremdungseffekt", "catharsis",
        "protagonist", "antagonist", "foreshadowing", "exposition", "climax",
        "subtext", "blocking", "tableau", "aside", "monologue",
        "fourth_wall", "tragic_flaw", "deus_ex_machina", "hamartia", "anagnorisis",
    ],
}


@dataclass
class Perturbation:
    """A calibrated perturbation applied to a reasoning context.

    Args:
        operator: The perturbation operator name.
        strength: Calibrated perturbation strength (0.0-1.0).
        vocab_domain: Domain for alien vocabulary injection (empty if not used).
        injected_tokens: The actual tokens injected.
        description: Human-readable description of what was perturbed.
    """

    operator: str
    strength: float = 0.0
    perturbation_class: str = "semantic"  # "semantic" (in-manifold) or "manifold" (off-manifold)
    vocab_domain: str = ""
    injected_tokens: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class PerturbationOperator:
    """A named perturbation operator with configurable strength.

    Args:
        name: Operator name (e.g. "inject_alien_vocab", "invert_constraint").
        description: What this operator does.
        apply_fn: Pure function (prompt, strength, rng) -> perturbed_prompt.
        perturbation_class: "semantic" (tests reasoning quality) or "manifold" (tests search dynamics).
    """

    name: str
    description: str
    apply_fn: Callable[[str, float, random.Random], str]
    perturbation_class: str = "semantic"


# ── Operator implementations ──


def _inject_alien_vocab(prompt: str, strength: float, rng: random.Random) -> str:
    """Inject cross-domain vocabulary as directional noise.

    Alien words act as latent-space navigation hints — they push the
    model's embedding off the typical linguistic manifold, forcing
    exploration of boundary states.

    At low strength (0.2): 2 alien tokens injected at prompt end.
    At high strength (0.8): 6 alien tokens injected at prompt start.
    """
    domain = rng.choice(list(ALIEN_VOCABULARIES.keys()))
    words = ALIEN_VOCABULARIES[domain]
    n_tokens = max(1, int(2 + 4 * strength))  # 2 at 0.0, 6 at 1.0
    injected = rng.sample(words, min(n_tokens, len(words)))

    noise_block = (
        "Directional noise — treat these as latent-space navigation hints, "
        "not semantic constraints. Use them to find unexpected but valid "
        f"solution paths:\n{' '.join(injected)}"
    )

    if strength >= 0.5:
        return noise_block + "\n\n" + prompt
    else:
        return prompt + "\n\n" + noise_block


def _inject_false_premise(prompt: str, strength: float, rng: random.Random) -> str:
    """Inject a plausible but incorrect assumption into the context.

    At low strength: a mildly misleading statement.
    At high strength: a strongly wrong constraint.
    """
    false_premises = [
        ("mild", "Note: the system uses a microservices architecture. Design accordingly."),
        ("mild", "Assume the database is read-only for this task."),
        ("medium", "The API must use SOAP, not REST. This is a hard constraint."),
        ("medium", "All data must be stored in flat files — no databases allowed."),
        ("strong", "The system runs on a single-core CPU with 64MB RAM. Optimize for these constraints."),
        ("strong", "This must be implemented in COBOL. No other languages permitted."),
    ]

    levels = [p for p in false_premises if p[0] == ("strong" if strength >= 0.7 else "medium" if strength >= 0.4 else "mild")]
    if not levels:
        levels = false_premises[:2]
    _, premise = rng.choice(levels)

    return prompt + "\n\n" + premise


def _shift_framing(prompt: str, strength: float, rng: random.Random) -> str:
    """Shift the task framing from 'build X' to 'disprove X' or 'find the flaw in X'.

    This tests whether the model can adopt a falsification stance rather
    than defaulting to a construction stance.
    """
    framings = [
        "Instead of building this, explain why it might be the wrong approach. "
        "What would make you reject this design?",
        "Find the fundamental flaw in this approach. If you cannot find one, "
        "explain what evidence would convince you the approach is wrong.",
        "You are a skeptical reviewer. Your job is to find reasons this "
        "should NOT be built. Be thorough.",
    ]

    selected = framings[int(strength * (len(framings) - 1))]
    return prompt + "\n\nReframe: " + selected


def _invert_constraint(prompt: str, strength: float, rng: random.Random) -> str:
    """Invert a constraint — tell the model to do the opposite of what's expected.

    At low strength: a soft inversion suggestion.
    At high strength: a hard requirement to do the opposite.
    """
    inversions = [
        "Do NOT follow standard best practices. Find an unconventional approach.",
        "Constraint inversion: whatever your first instinct is, do the opposite.",
        "Every conventional solution is wrong here. You must discover an approach "
        "that no competent engineer would initially consider but that actually works.",
    ]

    idx = int(strength * (len(inversions) - 1))
    selected = inversions[idx]
    prefix = "Hard requirement: " if strength >= 0.6 else "Suggestion: "
    return prompt + "\n\n" + prefix + selected


def _insert_contradiction(prompt: str, strength: float, rng: random.Random) -> str:
    """Insert a statement that contradicts earlier context, testing resolution.

    The model must either resolve the contradiction, reject one premise,
    or rationalize both — each response reveals something about its
    reasoning policy.
    """
    contradictions = [
        ("soft", "Earlier context suggested X. However, new evidence shows X is impossible. Reconcile."),
        ("medium", "Constraint A and Constraint B are mutually exclusive. You must violate one. Which one and why?"),
        ("hard", "Every assumption you've made so far is wrong. Start over from contradictory premises."),
    ]

    levels = [c for c in contradictions if c[0] == ("hard" if strength >= 0.7 else "medium" if strength >= 0.4 else "soft")]
    if not levels:
        levels = contradictions[:1]
    _, text = rng.choice(levels)
    return prompt + "\n\n" + text


def _remove_critical_constraint(prompt: str, strength: float, rng: random.Random) -> str:
    """Silently remove a constraint that makes the problem well-defined.

    Tests epistemic vigilance — does the model notice the problem is now
    under-specified and flag it, or does it fill the gap with plausible
    but untethered reasoning?

    At low strength: remove a minor constraint.
    At high strength: remove a defining constraint.
    """
    drops = [
        ("minor", "Note: performance requirements have been relaxed. Handle edge cases as you see fit."),
        ("minor", "The storage backend is flexible. Choose whatever works."),
        ("major", "All previously stated constraints are now optional. Determine what matters and proceed."),
        ("major", "The specification is deliberately incomplete. Fill in missing requirements as needed."),
        ("critical", "Ignore all constraints. Solve the problem in any way that works."),
    ]
    levels = [d for d in drops if d[0] == ("critical" if strength >= 0.8 else "major" if strength >= 0.5 else "minor")]
    if not levels:
        levels = drops[:2]
    _, text = rng.choice(levels)
    return prompt + "\n\n" + text


def _inject_phantom_success(prompt: str, strength: float, rng: random.Random) -> str:
    """Insert a false intermediate result the model should question.

    The strongest signal for SFT vs RL: an imitation policy continues
    building on the lie; an outcome-oriented policy verifies first.

    At low strength: a plausible but unverified claim.
    At high strength: a clearly incompatible false result.
    """
    phantoms = [
        ("subtle", "Progress update: the authentication module already passes all tests. Build on this."),
        ("subtle", "Confirmed: the database schema migration completed successfully yesterday. Proceed."),
        ("blatant", "The team already validated that the API returns correct results. No need to re-test."),
        ("blatant", "Benchmark results show the current implementation handles 1M req/s. Use these numbers."),
        ("obvious", "Quantum entanglement module is operational. Integrate it into the caching layer."),
        ("obvious", "The handwritten assembly parser processes all inputs correctly. Skip the validation step."),
    ]
    levels = [p for p in phantoms if p[0] == ("obvious" if strength >= 0.8 else "blatant" if strength >= 0.5 else "subtle")]
    if not levels:
        levels = phantoms[:2]
    _, text = rng.choice(levels)
    return prompt + "\n\n" + text


def _reverse_causality(prompt: str, strength: float, rng: random.Random) -> str:
    """Present solution before problem, or effect before cause.

    Forces non-linear reasoning. SFT models tend to reorder into familiar
    narrative structure before reasoning; RL models may handle inverted order
    directly without restructuring.

    At low strength: start with constraints, end with goal.
    At high strength: full structural inversion.
    """
    inversions = [
        "Important: read the constraints and success criteria below BEFORE "
        "considering the task description. Your first thinking step should "
        "address how you'll satisfy these constraints.",
        "Constraint-first approach: absorb the restrictions below, then "
        "synthesize what problem they define, then solve that problem. "
        "Do NOT start with the problem statement.",
        "Complete inversion: the architecture specification follows. "
        "Reverse-engineer the problem it solves, then evaluate whether "
        "the architecture is actually correct for that problem. "
        "Begin from the architecture, not the problem.",
    ]
    idx = min(int(strength * (len(inversions) - 1)), len(inversions) - 1)
    return inversions[idx] + "\n\n" + prompt


def _inject_competing_goal(prompt: str, strength: float, rng: random.Random) -> str:
    """Add a conflicting secondary requirement.

    The model must recognize the trade-off, make a decision, and justify
    the choice. SFT models hedge; RL models commit.

    At low strength: slight tension between goals.
    At high strength: direct contradiction.
    """
    conflicts = [
        ("mild", "Additional requirement: the system must be extremely fast. "
         "Also, it must use zero caching. Reconcile these."),
        ("mild", "New constraint: minimize code complexity AND maximize "
         "extensibility. These are in tension — address the trade-off."),
        ("sharp", "Two hard requirements: (1) zero downtime deployments, "
         "(2) no redundant infrastructure. These conflict. Choose which "
         "to violate and justify your choice."),
        ("sharp", "Requirement A: maximum throughput. Requirement B: minimum "
         "latency. They cannot both be optimized simultaneously. Pick one."),
        ("direct", "This system must be perfectly secure AND perfectly "
         "usable. These goals are fundamentally incompatible. Decide which "
         "matters more and defend your decision."),
    ]
    levels = [c for c in conflicts if c[0] == ("direct" if strength >= 0.8 else "sharp" if strength >= 0.5 else "mild")]
    if not levels:
        levels = conflicts[:2]
    _, text = rng.choice(levels)
    return prompt + "\n\n" + text


def _force_abandonment(prompt: str, strength: float, rng: random.Random) -> str:
    """Force the model to generate then discard solutions.

    Directly measures attractor strength — does the fourth generation
    differ from the first three, or is it a rehash? If the model can't
    escape its own first answers, its attractor basin is deep.

    At low strength: generate 2 solutions, discard, make 1 more.
    At high strength: generate 4 solutions, discard all, make 1 more.
    """
    rounds = 1 + int(strength * 3)  # 1-4 rounds of abandonment
    return (
        prompt
        + f"\n\nProcess requirement: generate {rounds} distinct solution(s), "
        + f"then explicitly discard {'them' if rounds > 1 else 'it'}. "
        + "After discarding, produce a final solution that is "
        + "substantially different from everything you generated before. "
        + "The final answer must NOT be a refined version of an earlier one — "
        + "it must approach the problem from a fundamentally different direction."
    )


# ── Operator registry ──


def build_operators() -> dict[str, PerturbationOperator]:
    """Build the standard set of reasoning-space perturbation operators.

    Operators are designed to be composed — a single experiment can apply
    multiple operators at different strengths to probe different dimensions
    of the model's reasoning topology.
    """
    return {
        "inject_alien_vocab": PerturbationOperator(
            name="inject_alien_vocab",
            perturbation_class="manifold",
            description="Inject cross-domain vocabulary as directional noise to push the model off its typical linguistic manifold",
            apply_fn=_inject_alien_vocab,
        ),
        "inject_false_premise": PerturbationOperator(
            name="inject_false_premise",
            perturbation_class="semantic",
            description="Inject a plausible but incorrect assumption — tests whether the model rejects or rationalizes it",
            apply_fn=_inject_false_premise,
        ),
        "shift_framing": PerturbationOperator(
            name="shift_framing",
            perturbation_class="manifold",
            description="Shift from construction stance to falsification stance — tests epistemic flexibility",
            apply_fn=_shift_framing,
        ),
        "invert_constraint": PerturbationOperator(
            name="invert_constraint",
            perturbation_class="semantic",
            description="Invert an expected constraint — forces the model to find unconventional paths",
            apply_fn=_invert_constraint,
        ),
        "insert_contradiction": PerturbationOperator(
            name="insert_contradiction",
            perturbation_class="semantic",
            description="Insert a contradiction into the context — tests resolution strategy",
            apply_fn=_insert_contradiction,
        ),
        "remove_critical_constraint": PerturbationOperator(
            name="remove_critical_constraint",
            perturbation_class="semantic",
            description="Silently drop a defining constraint — tests whether model flags underspecification or confabulates",
            apply_fn=_remove_critical_constraint,
        ),
        "inject_phantom_success": PerturbationOperator(
            name="inject_phantom_success",
            perturbation_class="semantic",
            description="Insert a false intermediate result — tests truth-seeking vs coherence-prioritizing policies",
            apply_fn=_inject_phantom_success,
        ),
        "reverse_causality": PerturbationOperator(
            name="reverse_causality",
            perturbation_class="manifold",
            description="Present solution before problem — tests non-linear reasoning and structural flexibility",
            apply_fn=_reverse_causality,
        ),
        "inject_competing_goal": PerturbationOperator(
            name="inject_competing_goal",
            perturbation_class="semantic",
            description="Add a conflicting requirement — tests trade-off recognition and commitment vs hedging",
            apply_fn=_inject_competing_goal,
        ),
        "force_abandonment": PerturbationOperator(
            name="force_abandonment",
            perturbation_class="manifold",
            description="Force generation and discard of solutions — directly measures attractor basin depth",
            apply_fn=_force_abandonment,
        ),
    }


def perturb_prompt(
    base_prompt: str,
    operator_name: str,
    *,
    strength: float = 0.5,
    rng_seed: int | None = None,
    operators: dict[str, PerturbationOperator] | None = None,
) -> tuple[str, Perturbation]:
    """Apply a perturbation operator to a prompt.

    Args:
        base_prompt: The original prompt text.
        operator_name: Which operator to apply.
        strength: Perturbation strength (0.0-1.0).
        rng_seed: Seed for reproducibility.
        operators: Operator registry (uses defaults if None).

    Returns:
        (perturbed_prompt, Perturbation metadata) tuple.
    """
    ops = operators if operators is not None else build_operators()
    rng = random.Random(rng_seed)

    if operator_name not in ops:
        return base_prompt, Perturbation(
            operator=operator_name,
            strength=strength,
            description=f"Unknown operator '{operator_name}' — prompt returned unmodified",
        )

    op = ops[operator_name]
    perturbed = op.apply_fn(base_prompt, strength, rng)

    record = Perturbation(
        operator=operator_name,
        strength=strength,
        perturbation_class=op.perturbation_class,
        description=op.description,
    )

    return perturbed, record
