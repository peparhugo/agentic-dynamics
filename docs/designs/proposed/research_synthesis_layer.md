---
status: proposed
---

# Research & synthesis layer — design (open web from day 1)

**Why.** The knowledge base holds *experience* (findings, patterns) and *self-knowledge*
(sessions/decisions), but no externally-sourced procedural knowledge. DeepSeek-class models are
weak exactly where the projects need them most — UI/UX (the external website refresh, SVG
handling, the Control Room), and no single source or single run is enough to teach that. The
missing layer is a **research → cluster → contemplation → synthesis → application** loop whose
unit is a *cluster of sources and a reasoned synthesis*, never "one page becomes one skill."

## Decisions taken (2026-09-10, controller)

1. **Open web from day 1** — not pinned-docs-only. Pinned/OSS sources remain the easy case, not
   the boundary.
2. **All three triggers** — demand-driven (the adapt loop emits a knowledge gap),
   controller-curated (the controller names a topic), autonomous (scheduled frontier work).
   One record shape, different `origin`.
3. **The agent judges its own sufficiency**, as a human would with real sources: no hard-coded
   minimum-source rule. The synthesis must RECORD the judgment — the sources it used, an
   independence assessment, its confidence, counter-evidence, and what would change its mind.
   The trace is what is reviewable, not a magic number.
4. **Verification by application first** — a synthesis is not declared "true"; it is applied to
   a real task (the first: a **Control Room facelift**) and judged by what happens. Once the
   pattern is trusted, application can become one signal among others rather than a gate.
5. **Both evaluation modes for UI work** — component/render tests AND a rubric with controller
   review. Neither alone is the bar.

## Record model (the unit of derived knowledge)

| Record | Shape | Authority / class |
|---|---|---|
| `research_request` | `origin` (adapt/controller/autonomous), question, acceptance criteria, status | [P]/[H] — a work order, not knowledge |
| `source_document` | uri, title, `fetched_at`, `sha256`, extracted text, fetch notes | `SOURCE`, `[X]` — quarantined from retrieval until cited by a synthesis |
| `synthesis` | question; cluster (source ids + independence assessment); consensus claims **each citing its sources**; disagreements preserved; chosen approach + rationale; confidence; sufficiency rationale; what-would-change-its-mind | `DERIVED`, `[C]`/`[H]`; `causes` → every cited source |
| `skill` | trigger (when this applies), procedure, evidence (synthesis id + sources), support/uncertainty | `DERIVED`, `[H]` (procedural) |
| `fact` / `policy` | declarative claim or constraint derived from a synthesis | `DERIVED`, `[C]`; never our `POLICY` (control rules stay ours) |

**Authority rules:** external material never becomes `POLICY` and never silently outranks our own
`MEASURED` findings; conflicts with measured evidence are recorded, not averaged. Web sources
carry freshness (pages change): `fetched_at` + a re-fetch/refresh path; stale syntheses are
re-researched, not trusted forever.

## Pipeline (the `research` workflow)

```
request → search → fetch (egress proxy) → cluster (dense+lexical, contradictions kept)
        → contemplate (synthesize: consensus, conflicts, chosen approach)
        → self-adversarial validate (entailment: every claim follows from its cited text;
          conflict scan against measured findings)
        → derive (skills / facts / task design brief)
        → apply (augmented task, measured)
```

* **Clustering is a first-class step**: sources are grouped by the claim/question they bear on,
  with disagreements preserved. A cluster feeds contemplation; a lone source does not conclude.
* **Contemplation is bounded and traced**: an agent pass with the sources in context; the
  synthesis artifact is the audit trail.
* **The self-adversarial pass** is the same adversarial pattern the build wave used: it may
  reject claims whose cited text does not entail them, and flags conflicts. It cannot invent
  consensus.

## Application pilots (first wave)

1. **Control Room facelift** — the first application. Research open-web UX/dashboard/control-room
   patterns (clusters: information hierarchy, data density, real-time telemetry affordances,
   accessibility), synthesize a concrete redesign brief for `apps/control_room/server.py` +
   templates, implement it on a feature branch (permanence gate applies), evaluate with
   component/render tests **and** a rubric + controller review. DeepSeek-augmented, measured
   against the current room.
2. **SVG handling** — the first *measured* pilot (unit-testable): research the SVG spec +
   real-world library behaviors/pitfalls, synthesize, derive a skill/brief, run a task family
   with vs without the synthesis. Clean quality signal; no subjective rubric needed.
3. **External website refresh** — follows once the brief format and the rubric are proven.

## Open items (to resolve in the wave design)

- Fetch mechanics and safety: egress scope, robots/ToS, rate limits, licensing of quoted text.
- Synthesis conflict policy: when measured evidence contradicts an external claim, which
  surfaces first in retrieval, and with what flag.
- Refresh cadence and versioning for web sources (the site changes; the synthesis must age).
- Retrieval representation for skills: v1 can ride the verified pattern-projection gate
  (procedural claims as pattern projections); a dedicated `skill` source_type is a later,
  separately-audited change.
- Evaluation harness for the Control Room: existing render/smoke checks vs new component tests
  (headless browser availability), plus the rubric dimensions.

## Relationship to scope 1 (flash-exploration)

Scope 1 (derive a skill from the ladder's own winning cells) and this layer share the **skill
representation and its retrieval gate**, built once. Scope 1 is the self-derived turn; this
layer is the externally-sourced turn; both end in the same place — an augmented generation arm
measured by the same instrument.
