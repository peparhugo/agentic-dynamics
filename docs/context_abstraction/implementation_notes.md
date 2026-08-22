# Context Abstraction Plane — Implementation Notes

**Append-only.** This file records the design deviations and verify-phase findings that the
implement spec (`workflows/repository/context_abstraction_implement.yaml`) must carry into
I0–I7. Never rewrite or delete an existing line — append new entries below the last one.

## 1. Addendum A reference (out of scope)

`docs/designs/current/context_abstraction_design.md` Addendum A (I8 profiles, I9 patterns,
I10 checkpoint) is OUT OF SCOPE for this spec; I8–I10 are implemented under a follow-up design
spec, not here.

## 2. F1 resolution (material)

An invariant with `on_missing: classify` silently disables a safety constraint — invariants
require halt semantics; the validator refuses a contract whose invariant lacks halt semantics
(new check documented under C8); the design's `max_spend_usd` example is amended: either
demote it from `invariants` to `requires_facts` or set `on_missing: halt`.

## 3. F2 resolution

Check C5 rejects an empty `facts_used`.

## 4. F3 resolution

`expected_effect` scores are recorded on the decision record, never applied.

## 5. F4 resolution

`conflicted` is computed in the reducer (`fact_state()`), read by the compiler.

## 6. F5 resolution

OQ3/OQ7 table-form answers accepted as-is.

## 7. F6 resolution

`source_type=fact` nominal authority column is documentation only — no change.
