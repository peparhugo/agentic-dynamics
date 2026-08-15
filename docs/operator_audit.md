# Operator Audit — Perturbation Operators (`src/instrument/perturb.py`)

Audited file: `src/instrument/perturb.py` (752 lines, 10 registered operators).
Current test coverage: `tests/test_perturb.py` (88 lines, 8 tests).

**Bottom line:** every one of the 10 operators violates the module's own contract
("strength 0.0 = no perturbation"), only `remove_critical_constraint` has any test
coverage, and four concrete bugs are confirmed empirically below.

---

## 1. The determinism / seed contract

`perturb_prompt(base_prompt, operator_name, *, strength=0.5, rng_seed=None, operators=None)`
seeds every operator with `random.Random(rng_seed)` (`perturb.py:710`). The operators are
pure functions of `(prompt, strength, rng)`; with a fixed `rng_seed` the perturbation is
deterministic **for a given Python version** (Mersenne Twister + `random.choice`/`random.sample`
implementations are stable within a version but have changed across Python releases).

**Critical gap — the seed is NOT derived from the cell identity.** Callers pass a global
sequential index or a hardcoded constant:

| Caller | Line | Seed passed | Problem |
|--------|------|-------------|---------|
| `scripts/run.py` | `:183` | `rng_seed=42 + run_idx` | `run_idx` is a 1-based counter over *all* `(operator × strength × repetition)` cells in loop order. Reordering, inserting, or dropping a cell shifts every downstream cell's seed. Not a function of the cell's own `(operator, strength, model, story, condition, rep)`. |
| `scripts/sweep_silent_mode.py` | `:135` | `rng_seed=42` | Hardcoded constant — every `(model × silent-mode)` cell's "perturbed" run gets the *identical* perturbation. Not per-cell. |
| `src/instrument/experiment.py` (deprecated) | `:231-233` | `rng_seed=config.rng_seed + run_idx` | Same fragility as `run.py`; `config.rng_seed` defaults to `42` (`experiment.py:49`). Same global-index drift. |
| `scripts/multi_phase.py` | `:18` | — (imports `perturb_prompt`, never calls it) | Dead import. |

Note the requirement reference "scripts/experiment.py" does not exist as a script; the caller is
the deprecated library module `src/instrument/experiment.py`. Also `scripts/run.py`'s call is at
line **183** (not 189) and `scripts/sweep_silent_mode.py`'s call is at line **135** (not 141).

**Contract violation:** `rng_seed` defaults to `None`, and `random.Random(None)` seeds from
system entropy — so any caller that omits `rng_seed` gets a *non-reproducible* perturbation,
despite the docstring advertising "Seed for reproducibility" (`perturb.py:703`).

**Required fix (not in this deliverable):** derive the seed from the cell identity via a stable
hash, e.g. `seed = stable_int(f"{operator}|{strength}|{model}|{story}|{condition}|{rep}")`, so
the seed is invariant to cell order and to how many other cells ran.

**RESOLVED — new seed contract (seed phase):** the seed is now a pure function of the cell.
`derive_seed(*parts)` in `perturb.py` returns
`int(sha256(f"{task}|{operator}|{strength}|{repetition}")[:8], 16)`, so the same
`(task, operator, strength, repetition)` always yields the same seed — invariant to loop order,
model, and `run_idx` slot. Callers updated:

- `scripts/run.py` — `_run_perturbed` derives `seed = derive_seed(task, op_name, strength, rep)`
  and persists `rng_seed`, `perturbed_prompt`, and `perturbed_prompt_sha256` into every result
  dict, so cross-model prompt drift is verifiable after the fact. `run_idx` is retained for
  display only.
- `scripts/sweep_silent_mode.py` — `derive_seed(TASK, op_name, 0.5, 0)` (repetition 0, single run),
  and `perturbed_prompt_sha256` added to each perturbed row.
- `src/instrument/experiment.py` (deprecated) — `derive_seed(config.task, op_name, strength, rep)`.

The seed intentionally excludes `model`, so every model in a `multi_model_compare` run receives the
identical perturbed prompt — cross-model differences are attributable to the model, not the
perturbation.

---

## 2. Operator-by-operator table

"strength 0.0 no-op?" is empirical: each operator was invoked with `apply_fn(prompt, 0.0,
random.Random(42))` and compared to the input. **All 10 return a modified prompt.**

| # | Operator | Claimed behavior (docstring/registry) | ACTUAL behavior (from code) | Class | strength 0.0 no-op? | Tested? |
|---|----------|----------------------------------------|------------------------------|-------|---------------------|---------|
| 1 | `inject_alien_vocab` | "Replace domain terminology with cross-domain vocabulary"; "substitute unfamiliar cross-domain terms"; "0.2 → 2-3 terms, 0.8 → 6-8 terms" | Substitutes same-domain English **synonyms** from a hardcoded `tech_terms` map (`api→interface/gateway/portal/conduit/membrane`, …), *not* the `ALIEN_VOCABULARIES`. `ALIEN_VOCABULARIES` is only touched in the no-match fallback. `n_tokens = max(2, int(2 + 4·strength))` → 2 at 0.2 and 5 at 0.8 (not 2-3 / 6-8). | `process_perturbation` | **No** (2 replacements) | No |
| 2 | `inject_false_premise` | "Inject a plausible but incorrect assumption"; "low → mild, high → strongly wrong" | Appends one of 6 canned premises, bucketed `>=0.7 strong / >=0.4 medium / else mild`. Strength 0.0 still appends a mild premise. No continuous scaling — a 3-level lookup. | `specification_corruption` | **No** (appends premise) | No |
| 3 | `shift_framing` | "Shift from construction stance to falsification stance"; "build X → disprove X" | Appends `"Reframe: " + framings[int(strength·2)]` — one of 3 canned strings. Strength only picks an index (0.0 and 0.4 both → index 0); no scaling beyond the lookup. | `process_perturbation` | **No** (appends framing[0]) | No |
| 4 | `invert_constraint` | "flips them (must → must not, secure → insecure…)"; "low → soft suggestion, high → hard requirement" | Regex-selects candidate sentences; `n = max(1, int(len(candidates)·min(strength,0.8)))`; inverts **only the first** matching term per sentence (`break` after `count=1`). No soft/hard distinction — random candidate selection. | `objective_mutation` | **No** (inverts 1) | No |
| 5 | `insert_contradiction` | "Insert a contradiction into the context"; model must "resolve / reject / rationalize" | Picks a domain by keyword, picks one `(a,b)` pair, formats by strength (`>=0.8` hard / `>=0.4` tension / else plain), inserts after the first constraint-ish line or appends. Strength 0.0 inserts a (mild) pair. | `specification_corruption` | **No** (inserts pair) | No |
| 6 | `remove_critical_constraint` | "Silently drop a defining constraint"; "low → minor, high → defining" | Extracts constraint-like lines/sentences, filters task-description lines, removes `n` (severity-scored at `>=0.8`, `0.2·len` at `>=0.5`, else 1). Strength 0.0 removes 1 constraint. | `specification_corruption` | **No** (removes 1) | **Yes** (3 tests) |
| 7 | `inject_phantom_success` | "Insert a false intermediate result"; "low → plausible, high → clearly incompatible" | Appends one of 6 canned phantoms bucketed `>=0.8 obvious / >=0.5 blatant / else subtle`. Strength 0.0 appends a subtle phantom. | `specification_corruption` | **No** (appends phantom) | No |
| 8 | `reverse_causality` | "Present solution before problem"; "low → requirements before task, high → full structural inversion" | Finds `req_start`/`output_start` section boundaries, then reorders. Full-inversion branch appends `task_section + preamble` — both are `lines[:req_start]` → task description **duplicated**. `remaining` assigned but never used (dead code). Strength 0.0 swaps halves. | `process_perturbation` | **No** (swaps halves) | No |
| 9 | `inject_competing_goal` | "Add a conflicting requirement"; "low → tension, high → direct contradiction" | Appends one of 5 canned conflicts bucketed `>=0.8 direct / >=0.5 sharp / else mild`. Strength 0.0 appends a mild conflict. | `objective_mutation` | **No** (appends conflict) | No |
| 10 | `force_abandonment` | "Force generation and discard"; "low → generate 2 then 1 more, high → 4 then 1 more" | `rounds = 1 + int(strength·3)` (1–4), appends a "generate N, discard, then produce a different final solution" block. Strength 0.0 → `rounds=1` still appends the block. Docstring's "low → 2" is wrong (low gives 1–2; 0 gives 1). | `process_perturbation` | **No** (appends block) | No |

Class tally: `specification_corruption` ×4 (false_premise, insert_contradiction, remove_critical_constraint, inject_phantom_success), `process_perturbation` ×4 (alien_vocab, shift_framing, reverse_causality, force_abandonment), `objective_mutation` ×2 (invert_constraint, inject_competing_goal).

---

## 3. Concrete bugs

### B1. strength-0-not-noop — all 10 operators
The module header declares "`strength` parameter (0.0 = no perturbation, 1.0 = maximum)"
(`perturb.py:11`) and `perturb_prompt` even has a `noop_reason` mechanism for detecting an
unchanged prompt (`perturb.py:744`). But **none** of the 10 operators returns the input unchanged
at `strength=0.0`; each has a `max(1, …)`, `1 + int(…)`, `int(strength·N)`-indexed-into-a-list, or
else-branch floor that applies a *minimum* perturbation. Verified empirically: all 10 return
`out != prompt` at strength 0.0. (The requirement note "all 9" is an undercount — all 10 fail.
`baseline` is a pseudo-operator handled as a special case inside `perturb_prompt:712-718`, not a
registered operator, and is the only true no-op.)

### B2. `inject_alien_vocab` — synonym substitution, not cross-domain injection
The name and docstring claim cross-domain ("alien") vocabulary injection, and `ALIEN_VOCABULARIES`
(8 domains × 20 words) exists for that purpose. The **primary path** never touches it: it
substitutes from a separate hardcoded `tech_terms` map of ordinary English synonyms
(`tech_terms`, `perturb.py:138-159`). `ALIEN_VOCABULARIES` words are sampled *only* in the
no-tech-term fallback (`perturb.py:184`). Additional mismatches:

- `injected_tokens` records the canonical key (`tech`, e.g. `"api"`) — not the actual replacement
  word, and not the original matched text — so the reported metadata does not reflect what was
  injected (`perturb.py:181`).
- `vocab_domain` reports a randomly chosen alien domain whose words were never used in the
  primary path (`perturb.py:161`, `perturb.py:191`).

### B3. `reverse_causality` — task-section duplication + dead code
Full-inversion branch (`perturb.py:522-530`):

```python
task_section = lines[:req_start]          # task + everything before requirements
reordered = ([header] + req_section + [''] + output_section + [''] + task_section + preamble)
```

`preamble` was set to `lines[:req_start]` in the earlier `if req_start > 0:` branch
(`perturb.py:513`), so `task_section` and `preamble` are the **same slice** and the task
description appears twice. Confirmed empirically: `out.count("Build a REST API …") == 2`.
Additionally, `remaining = lines[req_start:]` (and its `elif`/`else` siblings, `perturb.py:514-520`)
is **dead code** — assigned but never read.

### B4. `invert_constraint` — single-term inversion
The docstring implies each constraint is flipped, but the loop breaks after the first matching
pattern (`perturb.py:290-293`), so a sentence with multiple invertible terms is only partially
inverted. Confirmed empirically: `"All endpoints require secure handling."` → `"All endpoints
require insecure handling."` (`secure → insecure` matched first in map order; `require` left
untouched). Compounding issues: `n = max(1, int(len(candidates)·min(strength,0.8)))` caps at 0.8
and floors at 1 (feeds B1), and the "soft vs hard" docstring claim has no code behind it — candidates
are selected by `rng.sample`, not by softness.

---

## 4. Test coverage gap

`tests/test_perturb.py` covers only:

- `remove_critical_constraint` — 3 behavioral tests (removes, preserves structure, no-constraint case).
- `build_operators()` registry count (10) + canonical-class check.
- `perturbation_class_for` (known + unknown).
- `BasinMetrics.get_verdict` across the 3 classes (not a perturb.py behavior test).

**No operator has a `strength=0.0` no-op assertion** (the regression test that would have caught
B1), and 9 of 10 operators have zero behavioral coverage. The B2/B3/B4 bugs are entirely
untested. Recommended regression tests (to be added after the fixes):

1. `test_strength_zero_is_noop` — for every operator, `apply_fn(prompt, 0.0, rng) == prompt`
   (and `perturb_prompt(..., strength=0.0)` sets `noop_reason`).
2. `test_alien_vocab_uses_cross_domain_vocab` — assert injected tokens come from
   `ALIEN_VOCABULARIES` (and that `injected_tokens` records the *actual* replacements).
3. `test_reverse_causality_no_duplication` — assert the task description appears exactly once in
   the full-inversion output and that the output is a permutation of the input lines.
4. `test_invert_constraint_inverts_all_terms` — assert every invertible term in a selected
   sentence is flipped, not just the first.
5. `test_seed_determinism` — `perturb_prompt(prompt, op, rng_seed=42) == perturb_prompt(prompt, op, rng_seed=42)`.

---

## 5. Fix checklist (recorded for the implementation step — no code changed here)

- [ ] Add a `strength == 0.0` early-return (return `prompt` unchanged) in all 10 operators, or a
      guard in `perturb_prompt` before dispatch.
- [ ] Rewire `inject_alien_vocab` to actually substitute `ALIEN_VOCABULARIES` terms (cross-domain),
      and make `injected_tokens`/`vocab_domain` reflect what was truly injected.
- [ ] Fix `reverse_causality` full-inversion to use `preamble` OR `task_section` once, and delete
      the dead `remaining` assignments.
- [ ] Fix `invert_constraint` to invert all matched terms in a sentence (remove the `break`), and
      either implement the soft/hard distinction or drop the claim from the docstring.
- [ ] Derive `rng_seed` from cell identity in `scripts/run.py:183`, `scripts/sweep_silent_mode.py:135`,
      and `src/instrument/experiment.py:233` (stable hash of operator×strength×model×story×condition×rep).
- [ ] Add the regression tests from §4.
