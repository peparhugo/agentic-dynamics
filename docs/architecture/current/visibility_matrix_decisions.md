---
status: accepted
---
# Visibility Matrix — Decision Drafts (D1–D4)

**Status: accepted as DRAFTS.** Companion to `visibility_matrix.md` §5. These are the proposed
answers to its four open decisions, written for the addendum d4 adversarial review to ratify,
amend, or reject. Each decision states the recommendation, the reasoning, and the enforcement
consequence.

## D1 — Agent access to facts: **Option B (recommended) — agents retrieve patterns, never raw facts**

- **Option A (design status quo):** agents read knowledge records only; facts are for rules.
  Safe, but leaves the "leverage the entire learned system" gap — an agent session cannot read
  what the machine has measured.
- **Option B (recommended):** agents may retrieve **patterns** (I9 facts — compressed,
  uncertainty-carrying, citable: claim, population, conditions, support, uncertainty, validity
  window, source) via a retrieval-facing projection. Agents never retrieve raw facts
  (attempt-level rows, per-predicate values) — raw fact consumption stays address-based for
  controllers only.
- **Option C:** full fact retrieval for agents. Rejected: collapses the two-channel rule, invites
  stale/unsorted fact citation in prompts, and re-introduces the kitchen-sink the contract
  mechanism exists to prevent.
- **Reasoning:** a pattern is *experience compressed with its uncertainty attached* — exactly
  what a session should read when asking "what do we know about X?". A raw fact is *control
  truth* — the last thing a narrative agent should be citing mid-work. The asymmetry is the
  point: **agents read what we learned; controllers consume what is true.**
- **Enforcement:** patterns get a read-only RAG projection (D2); raw facts remain absent from the
  retrieval index (existing two-channel enforcement unchanged).

## D2 — Pattern projection: **a retrieval-facing knowledge record, never a fact-store duplication**

- **Shape:** `source_type="pattern"` knowledge record whose body IS the PatternPayload; authority
  DERIVED `[C]`; `acl_scope` default per the source domain; retrievable through the existing RAG
  path (Chroma + Neo4j → RRF) alongside reviews/findings.
- **Minting:** produced by the pattern reducer itself (hard rule 3 — deterministic, from measured
  evidence), not by an LLM. The projection is a *view* — one artifact per pattern fact,
  content-addressed, `knowledge_id` derived from the pattern fact's own id (no second identity).
- **Idempotency + staleness:** re-minting an unchanged pattern is a byte-identical no-op; when
  the underlying pattern fact is superseded (new validity window, new support), the projection
  supersedes with it — a projection can never outlive its fact.
- **What it is NOT:** not a duplicate row in the fact store (patterns remain facts; the
  projection is read-only for agents), not an LLM-written summary (advisory prose may attach as a
  separate field but is structurally uncitable, C5).
- **Open sub-question for d4:** should the projection carry the raw `source_experiment` refs
  (lab-contract style) so a retrieving agent can walk to the evidence? Recommended: yes — it is
  the provenance chain made agent-visible.

## D3 — Cross-repo isolation: **accept the repository boundary today; record the risk; revisit only on multi-domain**

- **Recommendation:** hold isolation by repository boundary + `repository_id` scoping + private
  ACL defaults for now (the personal-project posture), and record it as an accepted risk in the
  matrix's enforcement trace: the public framework's retrieval/reports/website could only
  surface private-repo rows if someone *copies them across* — machinery prevents nothing.
- **Escalation trigger:** if the framework ever hosts a second domain (or the investing repo
  grows shared-facing surfaces), add ACL enforcement at the retrieval + registry layers
  (scope-filtered queries) before any cross-domain surface ships.
- **Reasoning:** building ACL machinery now defends against a threat that does not exist (two
  domains in one store). The boundary is cheap, real, and sufficient at this scale; the
  enforcement gap is documented, not ignored.

## D4 — Operator fact plane: **Stage 6 Control Room surfaces, read-only**

- **Recommendation:** three read-only surfaces in the Control Room, built from the registry +
  reports (never from live session state):
  1. **Fact coverage view** — per predicate: `n_available/n_total`, PRODUCED/PARTIAL/UNOBSERVED
     verdicts (the backfill coverage doc rendered live).
  2. **Patterns view** — the I9 pattern facts: claim, support, uncertainty, validity window,
     source (D2 projection rendered for the operator).
  3. **Shadow-decision viewer** — the `applied: false` decision stream: decision, validation
     outcome (C1–C10), agreement vs `step_routing`.
- **Constraints:** display-only; operator has read access per the matrix; nothing in these views
  can steer a running session (the observe-only supervisor rail holds); built against the
  existing report scripts' outputs, not new live query paths.
- **When:** Stage 6, after the backfill populates the store and the shadow campaign #2 produces
  decision data worth viewing.

## Ratification record

| Decision | Draft | d4 verdict |
|---|---|---|
| D1 | Option B — agents retrieve patterns, never raw facts | _pending_ |
| D2 | read-only RAG projection, fact-derived, staleness-coupled | _pending_ |
| D3 | boundary today, escalate on multi-domain | _pending_ |
| D4 | Control Room: coverage + patterns + shadow views (Stage 6) | _pending_ |
