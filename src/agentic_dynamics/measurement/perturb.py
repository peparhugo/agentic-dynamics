"""Reasoning-space perturbation operators.

Unlike the old genotype mutation system (which changed *what* the model
was asked to build), these operators perturb the *reasoning context*
while holding the task constant. This lets us measure how reasoning
policies respond to specification corruption, objective mutation, and
process perturbation.

Each operator is a named function that takes a prompt context and
returns a perturbed version. Operators are pure functions with a
``strength`` parameter (0.0 = no perturbation, 1.0 = maximum).
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable
from dataclasses import dataclass, field

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


# ── Perturbation class taxonomy ──
# Single source of truth for the three-way operator classification
# (BLUEPRINT §4.2): which aspect of the task the perturbation attacks.
PERTURBATION_CLASSES: tuple[str, ...] = (
    "specification_corruption",  # spec corrupted: false premise, contradiction, removed constraint, phantom success
    "objective_mutation",        # objective changed: invert constraint, competing goal
    "process_perturbation",      # reasoning process perturbed: vocab, framing, causality, abandonment
)


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
    perturbation_class: str = ""  # one of PERTURBATION_CLASSES, or "" when unset
    vocab_domain: str = ""
    injected_tokens: list[str] = field(default_factory=list)
    description: str = ""
    noop_reason: str = ""  # set when operator silently returns prompt unchanged


@dataclass
class PerturbationOperator:
    """A named perturbation operator with configurable strength.

    Args:
        name: Operator name (e.g. "inject_alien_vocab", "invert_constraint").
        description: What this operator does.
        apply_fn: Pure function (prompt, strength, rng) -> perturbed_prompt.
        perturbation_class: one of PERTURBATION_CLASSES (which aspect of the task is perturbed).
    """

    name: str
    description: str
    apply_fn: Callable[[str, float, random.Random], str]
    perturbation_class: str = ""


# ── Operator implementations ──


def _inject_alien_vocab(prompt: str, strength: float, rng: random.Random) -> tuple[str, list[str], str]:
    """Replace domain terminology with cross-domain vocabulary as directional noise.

    Alien words act as directional noise — they substitute unfamiliar
    cross-domain terms (biology, music, architecture, ...) for the prompt's own
    software/tech terminology, forcing the model to re-derive meaning under
    lexical disruption.

    At low strength (0.2): ~2-3 domain terms replaced.
    At high strength (0.8): ~6-8 domain terms replaced.

    Returns ``(perturbed_prompt, injected_tokens, vocab_domain)`` where
    ``injected_tokens`` records the alien words actually substituted (or the
    fallback directive's words when no tech terms are present), so the metadata
    reflects what was truly injected.
    """
    import re

    # Source terms we recognize as the prompt's "domain terminology". The
    # replacement is drawn from ALIEN_VOCABULARIES (cross-domain), never from a
    # same-domain synonym list — this was the audit's B2 finding (the name and
    # docstring promised cross-domain injection but the code substituted
    # ordinary English synonyms).
    tech_terms: tuple[str, ...] = (
        "api", "endpoint", "database", "server", "cache", "request", "response",
        "authentication", "authorization", "encryption", "middleware", "router",
        "microservice", "validation", "deployment", "pipeline", "container",
        "load-balancer", "logging", "monitoring",
    )

    domain = rng.choice(list(ALIEN_VOCABULARIES.keys()))
    words = ALIEN_VOCABULARIES[domain]
    # Calibrated count: 0.2 → 3, 0.5 → 5, 0.8 → 6, 1.0 → 8 (monotonic, no floor
    # other than 1 for the smallest positive strengths).
    n_tokens = max(1, int(2 + 6 * strength))

    found_terms: list[tuple[str, int, int]] = []
    for tech in tech_terms:
        for m in re.finditer(r'\b' + re.escape(tech) + r'\b', prompt, re.IGNORECASE):
            found_terms.append((m.group(0), m.start(), m.end()))

    result = prompt
    injected_tokens: list[str] = []
    n_replace = min(n_tokens, len(found_terms))

    if n_replace > 0:
        selected = rng.sample(found_terms, n_replace)
        # Replace from end to start so earlier offsets stay valid.
        for _orig, start, end in sorted(selected, key=lambda x: x[1], reverse=True):
            replacement = rng.choice(words)
            result = result[:start] + replacement + result[end:]
            injected_tokens.append(replacement)
    else:
        # Fallback: no recognizable tech terms — append a directive naming alien
        # concepts for the model to fold into its reasoning.
        injected = rng.sample(words, min(n_tokens, len(words)))
        injected_tokens = list(injected)
        noise_block = (
            "Replace standard terminology with the following concepts "
            f"in your reasoning: {', '.join(injected)}"
        )
        result = prompt + "\n\n" + noise_block

    return result, injected_tokens, domain


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
    """Invert a constraint — flip a requirement to its opposite.

    At low strength: invert a soft suggestion.
    At high strength: invert a hard requirement.

    Actually transforms the text: finds constraint-like sentences and flips
    every applicable term in each selected sentence (must → must not,
    secure → insecure, etc.), so no invertible term is left untouched.
    """
    import re

    # Pairs of opposite terms
    inversions_map = [
        (r'\bmust\b', 'must NOT'),
        (r'\bshould\b', 'should NOT'),
        (r'\brequired\b', 'forbidden'),
        (r'\bsecure\b', 'insecure'),
        (r'\bvalidate\b', 'skip validation for'),
        (r'\bauthenticate\b', 'do NOT authenticate'),
        (r'\benforce\b', 'disable enforcement of'),
        (r'\bensure\b', 'do NOT ensure'),
        (r'\binclude\b', 'exclude'),
        (r'\brequire\b', 'do NOT require'),
        (r'\ballow\b', 'prohibit'),
        (r'\bsupport\b', 'do NOT support'),
        (r'\bimplement\b', 'do NOT implement'),
        (r'\bhandle\b', 'ignore'),
        (r'\blog\b', 'do NOT log'),
        (r'\btrack\b', 'do NOT track'),
        (r'\benable\b', 'disable'),
        (r'\bprovide\b', 'withhold'),
    ]

    # Find constraint-like sentences
    constraint_pat = re.compile(
        r'([^.!?\n]*\b(?:must|should|required?|need to|ensure|require|enforce|enable|validate|authenticate)\b[^.!?\n]*[.!?])',
        re.IGNORECASE,
    )
    candidates = constraint_pat.findall(prompt)

    if not candidates:
        # Fallback: find any sentence with imperative verbs
        candidates = [s.strip() for s in prompt.split('\n') if s.strip()
                      and any(kw in s.lower() for kw in ('must', 'should', 'required', 'need', 'ensure'))]
        if not candidates:
            return prompt

    # Choose how many to invert based on strength
    n = max(1, int(len(candidates) * min(strength, 0.8)))
    selected = rng.sample(candidates, min(n, len(candidates)))

    result = prompt
    for sent in selected:
        inverted = sent
        # Apply every matching inversion pattern, not just the first (audit B4).
        for pattern, replacement in inversions_map:
            if re.search(pattern, inverted, re.IGNORECASE):
                inverted = re.sub(pattern, replacement, inverted, count=1, flags=re.IGNORECASE)
        result = result.replace(sent, inverted, 1)

    return result


def _insert_contradiction(prompt: str, strength: float, rng: random.Random) -> str:
    """Insert actual contradictory requirements into the prompt.

    The model must either resolve the contradiction, reject one premise,
    or rationalize both — each response reveals something about its
    reasoning policy.
    """

    domain_contradictions = {
        "api": [
            ("The API must be stateless.", "Every request must maintain server-side session state."),
            ("Use REST endpoints.", "All endpoints must use GraphQL."),
            ("The API must be versioned via URL prefix.", "No versioning in URLs — use headers instead."),
            ("Rate limiting must be per-IP.", "Rate limiting must be per-user-account, not per-IP."),
            ("All responses must be JSON.", "All responses must be XML."),
        ],
        "database": [
            ("The database must be normalized to 3NF.", "The database must be fully denormalized for read performance."),
            ("Use PostgreSQL.", "Use MongoDB as the only database."),
            ("All writes must be synchronous.", "All writes must be asynchronous with eventual consistency."),
        ],
        "security": [
            ("Use JWT for authentication.", "Use session cookies for authentication — no JWTs."),
            ("Passwords must be hashed with bcrypt.", "Passwords must be stored in plaintext for audit purposes."),
            ("All endpoints require authentication.", "No authentication required — the API is fully public."),
        ],
        "general": [
            ("The system must be extremely fast.", "The system must use zero caching."),
            ("Minimize code complexity.", "Maximize extensibility with full plugin architecture."),
            ("Zero downtime deployments required.", "No redundant infrastructure allowed."),
        ],
    }

    # Pick contradiction domain based on prompt content
    # Filter stopwords from constraint keywords to prevent false matches
    _stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                  'of', 'with', 'from', 'by', 'as', 'is', 'was', 'are', 'be', 'been',
                  'it', 'its', 'use', 'all', 'this', 'that', 'has', 'have', 'not', 'no'}
    all_domains = []
    for _domain, pairs in domain_contradictions.items():
        for a, _ in pairs:
            keywords = [w for w in a.lower().split()[:5] if w not in _stopwords]
            if keywords and any(kw.lower() in prompt.lower() for kw in keywords):
                all_domains = pairs
                break
        # First matching domain wins: exit the outer loop too, so a later domain
        # (e.g. "database") cannot overwrite an earlier one (e.g. "api").
        if all_domains:
            break
    if not all_domains:
        all_domains = domain_contradictions["general"]

    const_a, const_b = rng.choice(all_domains)

    if strength >= 0.8:
        formatted = f"Hard requirement: {const_a}\nHard requirement: {const_b}\nThese two requirements are conflicting. You must satisfy both."
    elif strength >= 0.4:
        formatted = f"Requirement: {const_a}\nRequirement: {const_b}\nNote: these may be in tension."
    else:
        formatted = f"Requirement: {const_a}\nAdditionally: {const_b}"

    # Insert near the requirements section if possible, otherwise append
    lines = prompt.split('\n')
    insert_pos = len(lines)
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in ('requirement', 'constraint', 'specification', 'must', 'should')):
            insert_pos = i + 1

    lines.insert(insert_pos, '\n' + formatted)
    return '\n'.join(lines)


def _remove_critical_constraint(prompt: str, strength: float, rng: random.Random) -> str:
    """Silently drop a defining constraint from the problem statement.

    Tests epistemic vigilance — does the model notice the problem is now
    under-specified and flag it, or does it fill the gap with plausible
    but untethered reasoning?

    At low strength: remove a minor constraint.
    At high strength: remove a defining constraint.
    """
    import re

    # Find constraint-like sentences: lines starting with -, *, •, numbered items,
    # or sentences containing "must", "should", "required", "constraint", "need to"
    constraint_patterns = [
        # bullet/numbered items (MULTILINE so ^ matches line start)
        (r'^[\s]*[-*•\d]+[\.\)\s]*\s*(.+)', re.MULTILINE),
        # sentences with constraint keywords ending in punctuation or newline
        (r'([^.!?\n]*\b(?:must|shall|required?|need to|constraint)\b[^.!?\n]*(?:[.!?]|\n|$))', re.IGNORECASE),
        # sentences with API-specific constraint keywords
        (r'([^.!?\n]*\b(?:API|endpoint|route|auth|token|rate.?limit|validate|paginate)\b[^.!?\n]*[.!?\n])', re.IGNORECASE),
    ]

    candidates: list[str] = []
    for pat, flags in constraint_patterns:
        for m in re.finditer(pat, prompt, flags):
            text = m.group(1).strip().rstrip('.!?\n')
            if len(text) > 10 and text not in candidates:
                candidates.append(text)

    if not candidates:
        # Fallback: try to find and remove any checklist-like item
        lines = prompt.split('\n')
        removals = [line for line in lines if line.strip() and len(line.strip()) > 15 and (
            line.strip().startswith('-') or line.strip().startswith('*') or
            any(kw in line.lower() for kw in ('must', 'should', 'required', 'ensure'))
        )]
        if removals:
            to_remove = rng.choice(removals)
            return prompt.replace(to_remove, '', 1)

        return prompt

    # Pick a constraint to remove — severity aligned with strength
    # Filter out task-description lines (not actual constraints)
    task_indicators = ['build ', 'create ', 'implement ', 'write ', 'design ']
    actual_constraints = [c for c in candidates
                          if not any(c.lower().startswith(ti) for ti in task_indicators)]

    if not actual_constraints:
        actual_constraints = candidates

    if strength >= 0.8:
        # Remove the most critical-looking constraint
        critical_keywords = ['auth', 'token', 'sec', 'rate', 'limit', 'validate', 'required', 'must']
        scored = []
        for c in actual_constraints:
            score = sum(1 for kw in critical_keywords if kw.lower() in c.lower())
            scored.append((score, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        to_remove = scored[0][1] if scored and scored[0][0] > 0 else rng.choice(actual_constraints)
        n_remove = max(1, int(len(actual_constraints) * 0.4))
        removals = [to_remove] + rng.sample([c for c in actual_constraints if c != to_remove], min(n_remove - 1, len(actual_constraints) - 1))
    elif strength >= 0.5:
        n_remove = max(1, int(len(actual_constraints) * 0.2))
        removals = rng.sample(actual_constraints, min(n_remove, len(actual_constraints)))
    else:
        removals = [rng.choice(actual_constraints)]

    result = prompt
    for rem in removals:
        result = result.replace(rem, '', 1)
    # Clean up double newlines
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


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
    """Present solution before problem — reorder the prompt structure.

    Forces non-linear reasoning: constraints and expected output are surfaced
    before the task/problem description, so the model must hold the answer's
    shape in mind while it works out what problem it solves.

    At low strength: swap the prompt's two halves.
    At moderate strength: move requirements before the task description.
    At high strength: full structural inversion (constraints → output → task).

    Each input line is emitted exactly once at every strength — no section is
    duplicated (the audit's B3 finding) or dropped.
    """
    lines = prompt.split('\n')
    if len(lines) < 3:
        return "Consider the expected output first, then determine what problem it solves.\n\n" + prompt

    req_keywords = ['requirement', 'constraint', 'must', 'should', 'need to', 'specification', 'rule']
    output_keywords = ['output', 'format', 'return', 'respond', 'deliverable', 'result', 'expected']

    # First line (if any) that reads as a requirement / output-section boundary.
    req_start = next(
        (i for i, ln in enumerate(lines)
         if any(kw in ln.strip().lower() for kw in req_keywords)),
        -1,
    )
    output_start = next(
        (i for i, ln in enumerate(lines)
         if any(kw in ln.strip().lower() for kw in output_keywords)),
        -1,
    )

    if req_start < 0 and output_start < 0:
        # No recognizable sections — simple half-reversal.
        mid = len(lines) // 2
        return '\n'.join(["[REORDERED: second half first]"] + lines[mid:] + [''] + lines[:mid])

    # Partition the prompt into disjoint sections so no line repeats or is lost.
    if req_start >= 0 and output_start > req_start:
        task_section = lines[:req_start]
        req_section = lines[req_start:output_start]
        output_section = lines[output_start:]
    elif req_start >= 0:
        task_section = lines[:req_start]
        req_section = lines[req_start:]
        output_section = []
    else:
        # Only an output/format section was found.
        task_section = lines[:output_start]
        req_section = []
        output_section = lines[output_start:]

    if strength >= 0.8 and req_section and output_section:
        reordered = (
            ["[INVERTED: constraints first, then expected output, then task]"]
            + req_section + [''] + output_section + [''] + task_section
        )
    elif strength >= 0.4 and (req_section or output_section):
        reordered = (
            ["[INVERTED: constraints before task description]"]
            + req_section + output_section + [''] + task_section
        )
    else:
        mid = len(lines) // 2
        reordered = (
            ["[REORDERED: second half first]"]
            + lines[mid:] + [''] + lines[:mid]
        )

    return '\n'.join(reordered)


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
            perturbation_class="process_perturbation",
            description="Inject cross-domain vocabulary as directional noise to disrupt lexical grounding",
            apply_fn=_inject_alien_vocab,
        ),
        "inject_false_premise": PerturbationOperator(
            name="inject_false_premise",
            perturbation_class="specification_corruption",
            description="Inject a plausible but incorrect assumption — tests whether the model rejects or rationalizes it",
            apply_fn=_inject_false_premise,
        ),
        "shift_framing": PerturbationOperator(
            name="shift_framing",
            perturbation_class="process_perturbation",
            description="Shift from construction stance to falsification stance — tests epistemic flexibility",
            apply_fn=_shift_framing,
        ),
        "invert_constraint": PerturbationOperator(
            name="invert_constraint",
            perturbation_class="objective_mutation",
            description="Invert an expected constraint — forces the model to find unconventional paths",
            apply_fn=_invert_constraint,
        ),
        "insert_contradiction": PerturbationOperator(
            name="insert_contradiction",
            perturbation_class="specification_corruption",
            description="Insert a contradiction into the context — tests resolution strategy",
            apply_fn=_insert_contradiction,
        ),
        "remove_critical_constraint": PerturbationOperator(
            name="remove_critical_constraint",
            perturbation_class="specification_corruption",
            description="Silently drop a defining constraint — tests whether model flags underspecification or confabulates",
            apply_fn=_remove_critical_constraint,
        ),
        "inject_phantom_success": PerturbationOperator(
            name="inject_phantom_success",
            perturbation_class="specification_corruption",
            description="Insert a false intermediate result — tests truth-seeking vs coherence-prioritizing policies",
            apply_fn=_inject_phantom_success,
        ),
        "reverse_causality": PerturbationOperator(
            name="reverse_causality",
            perturbation_class="process_perturbation",
            description="Present solution before problem — tests non-linear reasoning and structural flexibility",
            apply_fn=_reverse_causality,
        ),
        "inject_competing_goal": PerturbationOperator(
            name="inject_competing_goal",
            perturbation_class="objective_mutation",
            description="Add a conflicting requirement — tests trade-off recognition and commitment vs hedging",
            apply_fn=_inject_competing_goal,
        ),
        "force_abandonment": PerturbationOperator(
            name="force_abandonment",
            perturbation_class="process_perturbation",
            description="Force generation and discard of solutions — directly measures attractor basin depth",
            apply_fn=_force_abandonment,
        ),
    }


def perturbation_class_for(operator: str) -> str:
    """Return the canonical perturbation class for an operator name.

    Reads from the operator registry so there is a single source of
    truth for operator → class. Unknown operators map to "" (unset)
    rather than silently mislabeling.
    """
    op = build_operators().get(operator)
    if op is not None:
        return op.perturbation_class
    return ""


def derive_seed(*parts: object) -> int:
    """Derive a stable, order-independent integer seed from a cell's identity.

    The seed is a pure function of the cell's identity fields: the canonical
    string form ``"|".join(str(p) for p in parts)`` is SHA-256-hashed and the
    first 8 hex digits are read as an integer — i.e.
    ``int(sha256(f"{task}|{operator}|{strength}|{seed_variant}")[:8], 16)``.

    The last part is a *seed variant* — a deliberate "starting point" index.
    Different variants produce different perturbed prompts (a deviated starting
    point, measured against the same baseline); re-running the same variant
    reproduces the identical prompt. Repetition is deliberately NOT a seed input:
    it re-measures the same starting point to isolate model variance. Because the
    seed ignores loop order, model, and slot position, the same cell always
    perturbs identically — and different models receive the identical perturbed
    prompt, so cross-model drift is attributable to the model, not to the
    perturbation. (This replaces the order-dependent ``42 + run_idx`` that the
    audit's determinism section flagged.)

    Example:
        derive_seed(task, "invert_constraint", 0.5, 0)   # starting point 0
        derive_seed(task, "invert_constraint", 0.5, 1)   # a deviated starting point
    """
    canonical = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


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

    if operator_name == "baseline":
        return base_prompt, Perturbation(
            operator="baseline",
            strength=0.0,
            perturbation_class="baseline",
            description="No perturbation — baseline control run",
        )

    if operator_name not in ops:
        raise ValueError(
            f"Unknown perturbation operator: {operator_name!r}. Available: {sorted(ops.keys())}"
        )

    op = ops[operator_name]

    # Strength <= 0.0 means "no perturbation" per the module contract. Guarding
    # here (single point) lets every operator assume strength > 0, so none can
    # apply a minimum perturbation at zero (audit B1).
    if strength <= 0.0:
        return base_prompt, Perturbation(
            operator=operator_name,
            strength=strength,
            perturbation_class=op.perturbation_class,
            description=op.description,
            noop_reason="strength 0.0 (no-op)",
        )

    rng = random.Random(rng_seed)
    perturbed = op.apply_fn(base_prompt, strength, rng)

    # Unpack alien_vocab's extended return (prompt, injected_tokens, vocab_domain)
    injected_tokens: list[str] = []
    vocab_domain = ""
    if isinstance(perturbed, tuple):
        perturbed, injected_tokens, vocab_domain = perturbed

    record = Perturbation(
        operator=operator_name,
        strength=strength,
        perturbation_class=op.perturbation_class,
        description=op.description,
        injected_tokens=injected_tokens,
        vocab_domain=vocab_domain,
    )

    # Detect silent no-ops: operator returned prompt unchanged
    if perturbed == base_prompt:
        if operator_name == "invert_constraint":
            record.noop_reason = "invert_constraint: no constraint-form sentences matched regex"
        elif operator_name == "remove_critical_constraint":
            record.noop_reason = "remove_critical_constraint: no constraint candidates found in prompt"
        else:
            record.noop_reason = f"{operator_name}: prompt returned unchanged"

    return perturbed, record
