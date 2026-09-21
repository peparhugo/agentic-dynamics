## lens_risks

# Evidence analysis — RISKS lens

*ARM B item-5 evaluation. Read-only: I read all four files under `evidence/` (and the two item-5 specs for context). No files edited, no mutating commands. Claims carry `file:line`; contradictions are kept rather than resolved by fiat. Because the lens is RISKS, I lead with what is most likely to fail next and then the findings it rests on.*

**Reasoning for shape (verbose mode).** Item 5 exists to decide whether four focused forks beat one broad analysis. The evidence already contains a two-wave natural experiment of exactly that pipeline — and its most consequential defect was not the analyses but the *transport of their inputs*. So a risks lens should rank delivery/provenance above interpretation, and should distrust any quality verdict built from the metrics that were substituted before.

## 1. Most important findings

**F1 — Both synthesis inputs were bounded, and the record now says so.** Wave-1's synthesis received the sixteen answers truncated to 4,000 chars each; wave-2's synthesis received *no sibling outputs* (`{prior_answers}` never inserted); therefore the syntheses are the least trustworthy documents in the package and the 24 raw answers are the material (`contemplation_waves_1_2_review.md:13-34`, `:101-117`; `aio_arc_findings_and_results.md:11-17`). Cross-sibling claims are bounded by the excerpt window (`contemplation_waves_1_2_review.md:76-85`).

**F2 — Delivery was the weak seam; the repairs are real but the proof is post-hoc.** The ledger did not persist phase responses (`PhaseResult.to_dict` omits `final_response`; `workflow_runner.py:283,356-422` per `contemplation_waves_1_2_review.md:26-29,49-52`), so answers were captured from the session store after the run (`:28-29`). The repair was verified once: `run-1ec7bb0052f0` delivered 24/24 complete (355,473 chars) with a manifest (`aio_arc_findings_and_results.md:153-158`; `contemplation_waves_1_2_review.md:127-134`), and emission was verified end-to-end including mid-report retrieval and link resolution (`aio_arc_findings_and_results.md:159-162`; `contemplation_waves_1_2_review.md:145-156`). Residual named gaps: no lineage labels in the manifest, prior syntheses cited second-hand (`contemplation_waves_1_2_review.md:133-134`).

**F3 — The arc's recurring failure pattern is "acceptance ≠ effect" / a cheap adjacent quantity standing in for the authority's own output.** Observed: the swallowed `fleet_manager restart` (claimed; queue and processing lane empty; no compose call; PID unchanged), "a queued submit is NOT a running run", the same-spec failing chain (`aio_arc_findings_and_results.md:174-177`), the capacity false trip at 172,491 vs 968,000 usable (`:170-171`), and three config-resolver divergences (`:172-173`). The "adjacent-quantity" pattern is framed as a pattern, not a law (`:223`).

**F4 — Retrieval does not carry the arc's analysis.** Corpus is fact-heavy (45,858/54,286 = 85%; findings 3,908) and last-24h findings spiked to 158 (`retrieval_audit.md:14-18`). "submission accepted versus work completed" returns spec-regeneration churn, not the failure pattern; only explicitly emitted records return (`:26-42`). Gaps ranked: emit opt-outs, scope pre-filter, thin retrieval-in-the-loop (`:44-52`). Updates: the CLI reader verb closes gap 3's CLI side (`:57-61`); all 20 `emit_self:false` flipped true (`:63-65`).

**F5 — The pilot is a ceiling null, and the strongest negative conclusions were rejected.** 12/12 accepted, no arm separated (`aio_arc_findings_and_results.md:100-111`); "contemplation should retire / provably ≤ 0" rejected on four grounds (`contemplation_waves_1_2_review.md:101-117`; `aio_arc_findings_and_results.md:199-200`); "unpromoted questions dropped, not stored" rejected (`:201-203`).

**F6 — The world-model loop is a proposal with three missing artifacts** (world-model artifact + contract, posterior diff, runtime-skill path) and an explicit "do not build a prose compiler / another governance framework" (`world_model_loop.md:45-55`; `aio_arc_findings_and_results.md:204-205`).

## 2. Most important risks / mistakes to avoid (ranked)

**R1 (highest) — The synthesis can silently lose its inputs again, and the run record cannot disprove it.** Item 5 is the same machinery that failed twice (`contemplation_waves_1_2_review.md:13-34`), the repair was verified once (`:127-134`), the manifest still has no lineage labels (`:133-134`), and the evidence *contradicts itself* on ledger persistence (`aio_arc_findings_and_results.md:227` vs `contemplation_waves_1_2_review.md:26-29`). A synthesis can read 24/24 files and still be uncheckable for *which complete text* it received. This is the most likely next failure because it is one silent fallback away at all times.

**R2 — The ARM A/B verdict will be overclaimed from weak proxies.** The pilot already sat at the acceptance ceiling (`aio_arc_findings_and_results.md:109-111`), and the controller rejected a "provably ≤ 0" claim built on exactly such a null (`contemplation_waves_1_2_review.md:105-113`). The real metrics — new validated findings, better decisions, misleading recommendations, controller reading/rework time (`aio_arc_findings_and_results.md:140-146`) — are not machine-checkable; the available substitutes are explicitly not quality: overlap "is not evidence that the answers contain different ideas" (`contemplation_waves_1_2_review.md:43-47`) and cache-read counts are counts, not hit rates (`aio_arc_findings_and_results.md:63-67`).

**R3 — Acceptance signals pass while the substance is clipped.** `derive_phase_record` keeps a canonical line + last line clipped to 200 chars; two different report bodies sharing a closing sentence produce identical extracted text (`contemplation_waves_1_2_review.md:136-143`). An "emission verified" claim can therefore coexist with an unretrievable finding.

**R4 — The emission flip floods the corpus and further degrades retrieval.** Facts already dominate 85% and findings spiked (`retrieval_audit.md:14-18`); all ~20 opt-outs were flipped to `emit_self: true` (`:63-65`); the audit's own standing question is "the corpus is only as good as what we emit" (`:54-55`). Unlabeled advisory findings can crowd out decisions.

**R5 — The pipeline scope pre-filter remains a silent zero.** Only the CLI side was closed; exact-match scope remains the rule and pipeline queries can still return 0 (`retrieval_audit.md:23-24,49-50,57-61`). A consumer that is not `knowledge read` can still conclude "nothing exists".

**R6 — Fork identity can silently mismatch.** "Forks must be transported, not assumed … never a silent fresh session" (`aio_arc_findings_and_results.md:218`); frozen real-session Docker forks remain unproven (`:229`); item5_B forks `ses_f5acb5440ffegDqoQONAP4AaR0` in-process (`specs/item5_B.yaml:31-33`). A fallback to a fresh session would make low overlap (`contemplation_waves_1_2_review.md:43-47`) a context artifact, not genuine divergence.

**R7 — The world-model pilot becomes prose with no diff target.** Without the artifact contract and posterior diff (`world_model_loop.md:45-55`), the pilot repeats the narrative-with-no-executable-output pattern the controller rejected (`contemplation_waves_1_2_review.md:119-125`); no local CI preflight exists (`world_model_loop.md:61-63`).

**R8 — Two adversarial rules, if implemented now, recreate known harm.** The `UCB95(−τ_g) > δ` context-dose hardening — the upper bound says harm remains *possible*, not established, and "could recreate the unwanted cutoff from inconclusive data" (`aio_arc_findings_and_results.md:206-209`; `contemplation_waves_1_2_review.md:113-117`); and treating cache/overlap/phase-ok as quality proof (`:43-47`; `aio_arc_findings_and_results.md:223`).

## 3. Disagreements preserved

- **D1 — Is `final_response` persisted on the ledger?** `aio_arc_findings_and_results.md:227` says it "is now persisted on the ledger"; `contemplation_waves_1_2_review.md:26-29` says neither run's ledger persists phase responses because `to_dict` omits it. Both documents are `status: accepted`. This must be resolved against the checkout before building on it.
- **D2 — Cache numbers.** `302,080` is a per-phase count, not a hit rate (`aio_arc_findings_and_results.md:63-67`; `contemplation_waves_1_2_review.md:36-41`), yet cache percentages are headlined (`aio_arc_findings_and_results.md:61`). Keep both readings.
- **D3 — Root cause of the 25-hour failure:** capacity-bounded vs compliance/looping (`aio_arc_findings_and_results.md:182-186` vs `:211-214`).
- **D4 — Loop rate; single authority vs resilience; value of human review; build breadth** (all open, `aio_arc_findings_and_results.md:211-214`).
- **D5 — Rejected-but-retained positions:** "retire contemplation" (`contemplation_waves_1_2_review.md:101-117`) and "unpromoted questions are dropped, not stored" (`aio_arc_findings_and_results.md:201-203`).

## 4. The single best next move, with its acceptance test

**Move: make delivered inputs provable in the run record before trusting the ARM A/B verdict — persist (or first verify the persistence of) each phase's complete response, plus a lineage-labeled delivery manifest, and require the synthesis to record what it received.** This is the precondition for the comparison item 5 exists to make; the failure already occurred twice (`contemplation_waves_1_2_review.md:13-34`); the current persistence claim is contradicted (`:26-29` vs `aio_arc_findings_and_results.md:227`); the missing lineage is named by the repair's own reviewers (`contemplation_waves_1_2_review.md:133-134`); and it is a bounded "missing regression check" using existing machinery (`aio_arc_findings_and_results.md:135-146`), not new governance.

**Acceptance test (ordered):**
1. **Resolve D1 first:** read `src/agentic_dynamics/runtime/workflow_runner.py` `PhaseResult.to_dict` (pinned at `workflow_runner.py:356-422` by `contemplation_waves_1_2_review.md:26-29`) and state whether `final_response` is persisted in the current checkout.
2. Run `specs/item5_B.yaml`; from the run ledger alone — no post-hoc session-store capture — show each phase's complete delivered payload (chars + sha256) and the synthesis's `answers_delivered` manifest with a **lineage label per answer**.
3. **Negative regression:** replay a truncated delivery (or cite `run-4d5feb401fd3` / `run-a2dbea18505c`, `contemplation_waves_1_2_review.md:11`) and require the check to FAIL with "incomplete delivery"; the historical unbounded synthesis is the fixture.
4. The synthesis cites each input by lineage label so cross-sibling agreement can be partitioned (the named next-iteration gap, `contemplation_waves_1_2_review.md:133-134`).

**Runner-up (if step 1 shows the delivery gap is already closed):** the controller's other bounded candidate — stale next-action state. A binding was still instructing "activate, then submit" after both had happened (`aio_arc_findings_and_results.md:179-180`), and the kept direction is "keep the existing task state current after confirmed actions" (`:188-192`). Acceptance: a regression test on the historical stale fixture fails, and a post-submit binding's next action is cleared/advanced.

## FINDING

The most likely next failure is that item-5's synthesis and its ARM A/B verdict rest on inputs whose completeness the run ledger still cannot prove: the two prior syntheses were input-bounded (4k excerpts; no sibling outputs), the repair was verified once, and the manifest lacks lineage labels (`contemplation_waves_1_2_review.md:13-34,127-134`). The evidence even contradicts itself on whether responses are persisted (`aio_arc_findings_and_results.md:227` vs `contemplation_waves_1_2_review.md:26-29`), so the gap is unverified today. Best move: make delivery provable in the run record — complete response plus lineage-labeled manifest — with a negative truncated-delivery regression; only then trust the comparison.

## lens_opportunities

Read all four evidence files (`aio_arc_findings_and_results.md`, `contemplation_waves_1_2_review.md`, `retrieval_audit.md`, `world_model_loop.md`). Analysis below, through the OPPORTUNITIES lens.

**Method note (read-only; verbose-mode rationale).** I did not edit or run anything mutating; every claim below is anchored to a file and line. I choose the opportunity framing deliberately: the evidence's own controller directions already enumerate risks and repairs, so the marginal value here is identifying the largest value not yet being realized. Where the evidence records unresolved disagreement, I keep it visible rather than resolving it by fiat.

---

## 1. Most important findings

**F1 — The project's newest loop is half-built: emission is now ON, consumption is still unmeasured.**
`evidence/retrieval_audit.md:63-66` (Update 2) records that all 20 `emit_self: false` opt-outs were flipped to `true`, so "Research/analysis runs now emit their reports as retrievable findings by default — the corpus should begin carrying analysis content, not just telemetry." But the same file's measured verdict (`:39-42`) is that "We do **not** retrieve the arc's analysis content … because those were never emitted," and its standing question (`:54-55`) is "Re-run this audit when the emission switches change." This is the single largest unrealized value: the switch is flipped, the content is being written, and no measurement yet shows it is retrievable.

**F2 — The delivery/emission plumbing is verified end-to-end, so the remaining gap is corpus content, not machinery.**
`evidence/contemplation_waves_1_2_review.md:127-134` (repair verified, `run-1ec7bb0052f0`: 24/24 answers delivered complete, 24/24 reads) and `:145-156` (emission verified: full report persisted, advisory finding `315a0c71…`, mid-report phrase retrieved via the real pipeline, evidence link resolves). `evidence/aio_arc_findings_and_results.md:227` confirms the same. Implication: the marginal cost of making every future analysis retrievable is now near-zero; the constraint is discipline + measurement.

**F3 — The corpus is telemetry-heavy; the curated layer is thin.**
`evidence/retrieval_audit.md:14-18`: 54,286 records, `fact` 45,858 (85%) vs `finding` 3,908; gap 2 (`:46-48`). The flip in F1 is the lever that can shift this mix; the audit is the instrument that shows whether it does.

**F4 — The reader verb exists, but the scope pre-filter makes empty priors look like empty corpora.**
`evidence/retrieval_audit.md:57-61` (Update: `knowledge read` + `knowledge-reader` skill built) against `:22-24` and gap 3 (`:49-51`): a scoped pipeline query can return **0** for generic queries because the pre-filter admits only exact-scope records. Any world-model "prior" (`evidence/world_model_loop.md:14-17`) must therefore carry an explicit scope or use the deterministic `--contains` fallback, or it will silently record nothing.

**F5 — The binding constraint on iteration is the operator's attention, not dollars.**
`evidence/aio_arc_findings_and_results.md:61-67` (arc spend ≈ $0.50; the relevant cost is "~55k words of answers for the controller to read"); `evidence/contemplation_waves_1_2_review.md:36-41` (two-wave total ≈ $0.236 for 26 outputs). Opportunity: structured emission (the now-wired path) plus summaries/dedup directly buys iteration rate.

**F6 — Two bounded improvements already have a controller-blessed direction and existing machinery.**
`evidence/aio_arc_findings_and_results.md:179-180` (a binding still instructing "activate, then submit" after both had happened) and `:190-191` ("keep the existing task state current after confirmed actions — the first fix"); `:197-198` (the alternative: a missing regression check), "after verifying the gap exists today."

**F7 — The pilot is a ceiling null; the next evaluation must pick a non-saturating oracle.**
`evidence/aio_arc_findings_and_results.md:109-111` (all four arms at the acceptance ceiling on one task — "not a 'measured disproof'") and `:222` ("binary oracles saturate"). Opportunity: measure the retrieval loop (F1), whose outcome is observable and not binary.

---

## 2. Most important risks / mistakes to avoid

**R1 — Adjacent-quantity substitution** (the arc's own named failure pattern): acceptance ≠ effect, green checks ≠ correct behavior, available context ≠ effective reasoning (`evidence/aio_arc_findings_and_results.md:168-171`). Concrete instances: the swallowed `fleet_manager restart` (claimed, queue and processing lane empty, no compose call, PID unchanged, `:173-175`) and "a queued submit is NOT a running run" (`:175-176`). **For this move:** an emission event or a flipped switch is not proof that analysis is retrievable.

**R2 — Do not build a generalized prose compiler or another governance framework** (`evidence/aio_arc_findings_and_results.md:204-205`), and runtime-minted skills must ride the same gate — never hand-edit generated surfaces (`evidence/world_model_loop.md:51-54`).

**R3 — Do not treat the syntheses as measured findings.** Wave-2's synthesis received no sibling outputs; wave-1's received 4,000-char excerpts; "the syntheses are the least trustworthy documents in this package" (`evidence/contemplation_waves_1_2_review.md:13-34`; `evidence/aio_arc_findings_and_results.md:126-134`).

**R4 — Do not harden a decision rule on inconclusive data.** The UCB95 context-dose rule means substantial harm remains *possible*, not established, and could "recreate the unwanted cutoff" (`evidence/aio_arc_findings_and_results.md:206-209`; source `wave2/c03:216-224`).

**R5 — Do not read a count as a rate.** 302,080 cache-read tokens/phase is a count, not a hit rate (`evidence/aio_arc_findings_and_results.md:63-67`; `evidence/contemplation_waves_1_2_review.md:36-41`).

**R6 — Do not assume Docker frozen-session snapshot transport works.** Three refusals, row-level extraction lost auxiliary data; the native export/import round-trip is proven, in-process is the used path (`evidence/aio_arc_findings_and_results.md:117`).

**R7 — Do not rely on clipped extraction.** `derive_phase_record` clips to 200 chars (canonical + last line); two reports sharing a closing sentence yield identical extracted text (`evidence/contemplation_waves_1_2_review.md:136-143`). Emit the full report as the finding text, report file as the evidence link.

**R8 — Do not let an empty retrieval look like an empty corpus.** Scope pre-filter behavior (`evidence/retrieval_audit.md:22-24,49-51`); record provenance and the exact query.

**R9 — Do not duplicate a parked/in-flight run.** The same-spec failing chain and the in-flight run are recorded (`evidence/aio_arc_findings_and_results.md:175-177`); acceptance is not a running run.

**R10 — Do not lose lineage.** The repair's own next-iteration gap: the delivery manifest carries no lineage labels, so corpus agreement cannot be partitioned by lineage (`evidence/contemplation_waves_1_2_review.md:131-134`).

**R11 — Read-only scopes cannot host runner writes; redirect transcripts/scratch to the state mount** (`evidence/aio_arc_findings_and_results.md:220`).

---

## 3. Single best next move — and its acceptance test

**Move: run the world-model loop's `PRIOR` on the arc's own material — concretely, re-run the retrieval audit's four exact queries through `knowledge read` now that emission is on, and persist the result as the prior's "known / unknown / what would reduce uncertainty" artifact.**

*Why this move (verbose rationale).* It is the cheapest executable test of the largest value line (F1); it is literally the pilot's first phase (`evidence/world_model_loop.md:58-60`); the audit itself requests it (`evidence/retrieval_audit.md:54-55`); it consumes only existing primitives, honoring the "do not build" direction (`evidence/aio_arc_findings_and_results.md:204-205`); and it chooses a non-saturating oracle (avoids F7's ceiling problem). It also doubles as a *bounded improvement*: the prior artifact is exactly the missing "what the run believed before it acted" (`evidence/world_model_loop.md:45-48`), and it can be emitted through the verified path (F2).

**Acceptance test (falsifiable, executable, negative half included):**
1. **Positive:** `agentic-dynamics knowledge read --query "submission accepted versus work completed" --scope agentic-dynamics` (plus the offline `--contains "submission accepted"` fallback) returns ≥1 `finding`/`report` record originating from newly emitted analysis whose text carries the acceptance-vs-completion pattern — and specifically **not** the four "138 specs changed" spec-churn findings the audit observed (`evidence/retrieval_audit.md:31-34`).
2. **Evidence-link:** a mid-report phrase from an emitted contemplation report retrieves that report's finding through the pipeline, and its evidence link resolves to the full text (mirrors `evidence/contemplation_waves_1_2_review.md:145-156`).
3. **Recorded provenance:** the re-run appends the measured corpus mix, the four queries' hits, and scope behavior to `retrieval_audit.md`; the prior artifact cites the exact query strings and record ids.
4. **Negative half (the honest failure):** if the query still returns only telemetry/spec churn, record that as the prior's top gap and **do not** proceed to synthesis or pilot-execute — the emission→retrieval loop is not yet real.

*Deliberately out of scope for this move:* Docker forks, the Q-B differential harness, and the world-model `execute`/`posterior` phases. Those are downstream of a prior that can actually retrieve, and R2/R4 caution against building them out of order.

---

## Disagreements preserved (not resolved here)

- **Root cause of the 25-hour failure:** compliance/looping vs capacity-bounded (`evidence/aio_arc_findings_and_results.md:182-184,212-214`; wave1/c11,c13 vs the directive).
- **Loop rate:** every turn vs the plant's time constant (`:211-212`).
- **Single authority vs resilience:** (`:212-214`; wave1/c04,c14 vs c05,c12).
- **Human review's value:** wave1/c08,c09 vs wave2/c05 (`:213-214`).
- **Build breadth:** wave1/c09 vs c07 vs wave2/c01 (`:214`).
- **"Retire further contemplation":** the wave-2 synthesis's conclusion is explicitly **rejected** by the controller (`:199-200`; `evidence/contemplation_waves_1_2_review.md:101-117`).
- **Q-B harness status:** "recurrence-insurance, not a review replacement" (`evidence/contemplation_waves_1_2_review.md:112-114`); the UCB95 dose rule still needs technical review (`evidence/aio_arc_findings_and_results.md:206-209`).

---

## FINDING

The project's biggest unrealized value is its newest half-loop: the emission switch was just turned on for every analysis spec (evidence/retrieval_audit.md:63-66), yet nothing measures that the newly emitted analysis is retrievable — the audit's verdict was that we retrieve code symbols and telemetry, not the arc's failure-pattern wisdom (evidence/retrieval_audit.md:39-42). The world-model loop's `prior` step is the natural consumer (evidence/world_model_loop.md:14-17). Best next move: run the prior as the audit re-run, accepting it only when the query "submission accepted versus work completed" returns the arc's pattern from an emitted finding and a mid-report phrase resolves to full text; otherwise record the empty retrieval as the prior's top gap and stop.

## lens_contradictions

I read all four evidence files in full (`aio_arc_findings_and_results.md`, `contemplation_waves_1_2_review.md`, `retrieval_audit.md`, `world_model_loop.md`). Read-only: no files edited, no mutating commands. Below, every claim carries a `evidence/<file>:<line>` anchor, and the lens is contradictions — I name the pairs explicitly and preserve the open disagreements rather than resolving them silently.

---

## 1. Most important findings (grounded)

**F1 — The arc's headline conclusions outran its evidence, and the mechanism is now named.** The wave-1 synthesis received the sixteen sibling answers only as 4,000-char excerpts (`evidence/contemplation_waves_1_2_review.md:16-19`; `evidence/aio_arc_findings_and_results.md:126-130`), and the wave-2 synthesis received **no sibling outputs at all** because its prompt never inserted `{prior_answers}` (`evidence/contemplation_waves_1_2_review.md:20-25`). The syntheses are therefore the least trustworthy documents in the package (`...:29-34`). "Retire further contemplation / narrative waves provably ≤ 0" is rejected (`evidence/aio_arc_findings_and_results.md:13-17,199-205`; `...:101-117`). The most important *epistemic* finding is not the plan outcome — it is that an input-starved synthesis looked authoritative until the controller's review caught it.

**F2 — The delivery repair is real and independently verified.** The repaired channel persisted `final_response`, delivered all 24 answers complete (355,473 chars) as a workspace file bundle with an `answers_delivered` manifest, and `run-1ec7bb0052f0` made 24/24 read calls (transcript-verified) (`evidence/contemplation_waves_1_2_review.md:127-134`; `evidence/aio_arc_findings_and_results.md:153-158,227`). Emission end-to-end was verified separately (registry line + mid-report retrieval + evidence-link resolution, `...:145-156`). So the pipeline *can* carry analysis; the missing piece is configuration and the second blocker below.

**F3 — The audit's measured reality: the KB is mostly telemetry.** 54,286 records, `fact` 45,858 (85%), `finding` 3,908 (`evidence/retrieval_audit.md:14-17`). Four real queries returned code symbols, registry/spec-churn, spine records, and only explicitly-emitted findings; the arc's central failure pattern is *not in the KB* (`...:28-42`). Scoped queries can return 0 under the exact-match pre-filter (`...:23-24,49-50`); retrieval-in-the-loop is enabled by only 8 specs (`...:51-52`). **Arithmetic check:** the category counts sum to 54,103, not the stated 54,286 — a 183-record gap (`...:14-16`); only the lifecycle figures (52,303 + 1,470 + 513) reach 54,286.

**F4 — The capacity-budget defects are measured, dated, and fixed — but acceptance is not effect.** The false trip refused a valid session at WARN 172,491 against 968,000 usable (`evidence/aio_arc_findings_and_results.md:170-171`); three config-resolver divergences were reproduced (`...:172-173`). Against that, the swallowed `fleet_manager restart` (queue empty, no compose call, PID unchanged), "a queued submit is NOT a running run", and the same-spec failing chain are all recorded (`...:174-177`).

**F5 — The pilot is a ceiling null, not a disproof.** 12/12 accepted across four arms on one task (`evidence/aio_arc_findings_and_results.md:100-111`); the package itself says this is not a "measured disproof" that instruction prose cannot change outcomes (`...:109-111`; `evidence/contemplation_waves_1_2_review.md:105-107`).

**F6 — The world-model loop is a controller direction, still `status: proposed`, with all three core artifacts absent.** "Nothing today persists 'what the run believed before it acted'… no phase/step compares model vs outcome" (`evidence/world_model_loop.md:6-7,13-28,45-54`). Its "smallest next steps" include a prior→execute→posterior pilot and a plan→DAG bridge (`...:56-76`).

## 2. Contradiction pairs (the lens — named)

1. **"No KB emission today" vs "emission verified."** `evidence/aio_arc_findings_and_results.md:228` (accepted, §6: "Contemplation outputs produce no KB emission today… the emit hook requires `pr.commit_hash`") versus `evidence/aio_arc_findings_and_results.md:159-162` and `evidence/contemplation_waves_1_2_review.md:145-156` (emission verified end-to-end). Same package, same date range; the accepted record contradicts its own §4.3.
2. **"Analysis specs opt out" vs "all 20 opt-outs flipped."** `evidence/retrieval_audit.md:46` and Update 2 (`...:63-66`: "all 20 `emit_self: false` opt-outs were flipped… now emit their reports as retrievable findings by default") versus `evidence/aio_arc_findings_and_results.md:228` and `evidence/contemplation_waves_1_2_review.md:152` (research_readonly, no commits).
3. **"Gap 3 closed" while the rule is unchanged.** `evidence/retrieval_audit.md:57-61` ("Gap 3's CLI side is closed… The scope rules are unchanged (exact-match pre-filter)") versus the gap it claims to close at `...:23-24,49-50` (scoped queries return 0). A reader verb plus an explicit-scope override is not a fix to the pre-filter.
4. **"Self-contained" vs "not carried by this branch."** Title `evidence/aio_arc_findings_and_results.md:5` versus its own §2, four times: "(artifact: local KB store, not carried by this branch)" (`...:73,77,81,85`).
5. **Cache percentages vs the caveat that they are not percentages.** Headline "input cache 95.5–97.9%" and "47% → 90% warm" (`evidence/aio_arc_findings_and_results.md:61,116`) — and `cache_hit_rate` 0.91–0.98 cited in `evidence/contemplation_waves_1_2_review.md:37-41` — versus "It is not a hit percentage… only as good as its denominator" (`evidence/aio_arc_findings_and_results.md:63-67`; `...:37-41`).
6. **The harness "cheaper than the review" vs "recurrence-insurance, not a review replacement."** `evidence/contemplation_waves_1_2_review.md:91` (c01's entry claim) versus `...:113` (the kept conclusion). This pair is reported and left unreconciled.
7. **"Emit by default" vs "path now wired."** `evidence/retrieval_audit.md:63-66` and `evidence/world_model_loop.md:60` ("the emission path is now wired") versus `evidence/aio_arc_findings_and_results.md:228` — a September-21 status asserted over a September-20 accepted record that still says otherwise.
8. **Retrieval-in-the-loop: capability vs gap.** Listed as an existing primitive "enabled by 8 specs" (`evidence/world_model_loop.md:37`) versus ranked gap 4, "most phases never retrieve at all" (`evidence/retrieval_audit.md:51-52`).
9. **Anti-framework direction vs the proposed build.** "Do not build a generalized prose compiler or another governance framework" and "one bounded improvement using existing machinery" (`evidence/aio_arc_findings_and_results.md:146,136-140,204-205`) versus the three-artifact loop, runtime-skill path, and plan→spec/DAG bridge (`evidence/world_model_loop.md:45-76`). Both trace to the controller (`...:7`), so the contradiction is between two controller directions, not an agent overreach.

## 3. Most important risks / mistakes to avoid

- **R1 — Concluding from an unverified delivery.** The exact repeatable defect: no manifest, no lineage labels, ledger omits `final_response` (`evidence/contemplation_waves_1_2_review.md:26-29,132-134`). Any synthesis conclusion must be gated on a recorded delivery manifest.
- **R2 — Building the world-model loop on an unverified retrieval layer.** E4 depends on `knowledge read` returning analysis (`evidence/world_model_loop.md:13-19,34-37`), yet the last measurement says analysis is absent (`evidence/retrieval_audit.md:39-42`) while the same file predicts it should now appear (`...:63-66`). Building the prior/posterior artifacts before re-measuring risks a framework over an empty corpus — and collides with the anti-framework direction (`evidence/aio_arc_findings_and_results.md:146,204-205`).
- **R3 — Mistaking derived metrics for quality.** Cache percentages (`evidence/aio_arc_findings_and_results.md:63-67`), acceptance saturation (the pilot ceiling, `...:109-111`), and "ten green checks for correct behaviour" (`evidence/contemplation_waves_1_2_review.md:78-80`). The record itself warns: cache reuse "never proof of better work; binary oracles saturate" (`evidence/aio_arc_findings_and_results.md:222`).
- **R4 — Leaving stale operational state.** A binding still instructing "activate, then submit" after both had happened (`evidence/aio_arc_findings_and_results.md:179-180`), and restart receipts that don't exist (swallowed restart, `...:174-176`). This is the controller's own first bounded-fix candidate (`...:197-198`).
- **R5 — Reading truncated syntheses or second-hand citations as primary evidence.** The 4k-window bound (`evidence/contemplation_waves_1_2_review.md:82-85`) and the missing lineage labels (`...:132-134`) make cross-sibling agreement unpartitionable; only the raw answers are primary (`...:30-31`).

## 4. Preserved disagreements (not resolved here)

Loop rate — every turn vs the plant's time constant; single authority vs resilience; capacity vs compliance as root cause; human review's value; build breadth (`evidence/aio_arc_findings_and_results.md:211-214`). Plus the pairs in §2 (6, and the emission status) which the package leaves standing. The wave-2 upper-bound rule hardening on `UCB95(−τ_g) > δ` is explicitly "needs technical review" — it could recreate the unwanted cutoff (`...:206-209`; `evidence/contemplation_waves_1_2_review.md:113-117`).

## 5. Single best next move, with acceptance test

**Re-run the standing retrieval audit against the current corpus, using the audit's own four queries** (`evidence/retrieval_audit.md:9-10,26-37`). Reasoning: it is the cheapest falsifier of the highest-stakes contradiction in the package — the claim that flipping the emission switches made analysis retrievable (`evidence/retrieval_audit.md:63-66`; `evidence/world_model_loop.md:60`) versus the accepted record's "no emission today" (`evidence/aio_arc_findings_and_results.md:228`) — and it is the explicit precondition the audit sets for itself ("re-run whenever the corpus or the emission switches change", `evidence/retrieval_audit.md:9-10`). It is also a precondition for E4: the world-model prior reads the corpus, so its value is bounded by this result. It is read-only and uses existing machinery; it does not build anything.

**Acceptance test.** Run the four audited queries verbatim (`evidence/retrieval_audit.md:28-37`). Pass requires: (a) `"submission accepted versus work completed"` returns the arc's failure-pattern analysis rather than four `138 specs changed` registration-churn findings (`...:31-33`); (b) at least one finding emitted from a research/analysis phase is retrievable by a phrase from the middle of its report, with its evidence link resolving to the full text (the shape verified at `evidence/contemplation_waves_1_2_review.md:151-156`); and (c) the count of `finding` records and analysis-origin records increases versus the first audit's 45,858 facts / 3,908 findings (`evidence/retrieval_audit.md:14-16`). **Fail** names the first blocker — the `pr.commit_hash`/`research_readonly` gate (`evidence/aio_arc_findings_and_results.md:228`) or the exact-match scope pre-filter (`evidence/retrieval_audit.md:23-24`) — and that blocker becomes the next bounded fix, before any world-model work.

## FINDING

The package's own corrections show the arc's conclusions repeatedly outran its evidence: syntheses were authoritative-looking yet input-starved (`evidence/contemplation_waves_1_2_review.md:16-34`), and the accepted record still asserts "no KB emission today" (`evidence/aio_arc_findings_and_results.md:228`) while the same package and the proposed loop declare emission wired (`evidence/retrieval_audit.md:63-66`, `evidence/world_model_loop.md:60`). The live corpus remains 85% facts with analysis unretrieved (`evidence/retrieval_audit.md:14-42`). The recurring defect is asserting completion from a switch flip, not from a measured retrieval. Re-run the standing audit before trusting any retrieval-dependent plan.

## lens_next_moves

I read all four evidence files plus the task specs (`specs/item5_A.yaml`, `specs/item5_B.yaml`) and the delivered corpus index (`.instrument/delivery-answers/`). Below is the NEXT-MOVES lens output. Every claim carries its file:line anchor.

# Next-moves analysis — AIO arc evidence (lens: NEXT MOVES)

## Method and framing (why this shape)

The evidence has an explicit error history: the two wave syntheses were presented as findings before their **delivery bound** was known (`evidence/aio_arc_findings_and_results.md:11-17`; `evidence/contemplation_waves_1_2_review.md:13-34`). So I treat the **individual answers as primary** (`contemplation_waves_1_2_review.md:30-31`), treat syntheses as advisory, and score my own recommendation only against claims that are anchored to a run, a code path, or a corpus count. The task's own specs set `budget_usd: 0.10`, `fork_session: ses_f5acb5440ffegDqoQONAP4AaR0` (`specs/item5_B.yaml:15,32`), and this arm's lens is literally "NEXT MOVES … single best next move, with its acceptance test and cost" (`specs/item5_B.yaml:65`).

## (1) Most important findings

1. **One failure class, stated three ways: the proxy displaced the authority's own output.**
   - The capacity false trip: a valid session refused at `WARN 172,491` against `968,000` usable (`evidence/aio_arc_findings_and_results.md:170-171`).
   - Three config-resolver divergences: `OPENCODE_CONFIG` precedence, a partial `output` override discarding inherited `context`, JSONC trailing commas (`aio_arc_findings_and_results.md:172-173`).
   - Acceptance ⇒ effect: the **swallowed `fleet_manager restart`** (claimed; queue and processing lane empty; no compose call; PID unchanged), and "a queued submit is NOT a running run" (`aio_arc_findings_and_results.md:174-177`).
   - The named pattern for all of this is the **adjacent-quantity substitution**: `200,000` for capacity, an empty queue for a completed dispatch, ten green checks for correct behaviour (`aio_arc_findings_and_results.md:77-81`, `:222`).

2. **The synthesis-delivery correction is the most important epistemic finding, because it invalidates the strongest prior conclusion.**
   - Wave-1 synthesis (`c17`) read siblings only through a 4,000-char window (`workflow_runner.py:4844-4849`; `contemplation_waves_1_2_review.md:16-19`); wave-2 synthesis (`w2c09`) received **no sibling outputs** — its prompt never inserted `{prior_answers}` (`contemplation_fanout_v2.yaml` L321-326; `contemplation_waves_1_2_review.md:20-25`), and says so itself (`wave2/c09.md:53`).
   - Consequence drawn by the review: the syntheses are "the least trustworthy documents in this package"; "contemplation should retire itself" is **unsupported and rejected** (`aio_arc_findings_and_results.md:11-17`, `:198-203`; `contemplation_waves_1_2_review.md:104-117`).

3. **The delivery and emission repairs are real and verified — measured, not asserted.**
   - Answer delivery: all 24 answers complete (355,473 chars) via a workspace-internal file bundle + manifest; 24/24 read calls transcript-verified; the single-argv E2BIG cap (~128 KB) explained the truncation (`aio_arc_findings_and_results.md:153-158`, `:227`; `contemplation_waves_1_2_review.md:127-134`).
   - Emission: the runner persists the fork's complete turn as a durable report and emits an advisory `phase-report/v1` finding whose text **is** the report; mid-report retrieval and link resolution verified end-to-end (`aio_arc_findings_and_results.md:159-162`; `contemplation_waves_1_2_review.md:145-156`).

4. **Retrieval reality check: the corpus is mostly telemetry, and the arc's own lesson was not in it.**
   - Corpus: 54,286 records; `fact` 45,858 (85%), `finding` 3,908 (`evidence/retrieval_audit.md:14-18`).
   - Query `"submission accepted versus work completed"` returned spec-index regeneration churn — "the arc's central failure pattern is *not* in the KB" (`retrieval_audit.md:29-31`).
   - Gap 1 (analysis specs opted out with `emit_self: false`) is now flipped for all tracked specs; Gap 3's CLI side is closed by `knowledge read --query Q --scope S` (`retrieval_audit.md:57-65`). So the corpus is only now positioned to carry analysis.

5. **The next-loop design is named and its missing artifacts are enumerated (proposed, not built).**
   - prior → plan → execute → posterior, with the posterior as violations/unknowns/updates; "the contemplation fan-out + synthesis is this step's experimental form" (`evidence/world_model_loop.md:5-28`).
   - Three missing artifacts: the world-model artifact + contract, the posterior diff, the runtime skill path (`world_model_loop.md:45-55`); the smallest pilot is a three-phase `agent_task` with prior/posterior artifacts persisted and emitted (`world_model_loop.md:56-60`).

6. **Economics and the attention bound.** Arc model spend ≈ $0.50; wave 1 `17/17` $0.14184, wave 2 `9/9` $0.09423; `302,080` cache-read tokens/phase is a **count, not a hit rate** (`aio_arc_findings_and_results.md:61-67`; `contemplation_waves_1_2_review.md:36-41`). The real cost is the controller's attention (~55k words of answers — `aio_arc_findings_and_results.md:67`).

## (2) Most important risks / mistakes to avoid

1. **Substituting a proxy for the authority (the adjacent-quantity substitution).** Do not report a proxy as the thing: an empty queue for a completed dispatch, `queued` for `running`, a derived `cache_hit_rate` for measured reuse, green checks for correct behaviour (`aio_arc_findings_and_results.md:77-81`, `:63-67`, `:174-177`, `:222`).
2. **Trusting the syntheses past their delivery bound.** Any cross-sibling claim inherits the 4k-char window (wave 1) or absence (wave 2); the review already rejected the strongest such claim (`contemplation_waves_1_2_review.md:13-34`, `:104-117`).
3. **Hardening policy on inconclusive data.** The context-dose rule keyed on `UCB95(−τ_g) > δ` can "harden from inconclusive data and recreate the unwanted cutoff" — it needs technical review before implementation (`aio_arc_findings_and_results.md:206-209`).
4. **Building frameworks/prose compilers.** Explicitly prohibited: "Do not build a generalized prose compiler or another governance framework" (`aio_arc_findings_and_results.md:204-205`); the build-breadth disagreement is preserved (`:214`).
5. **Reading a saturated oracle as disproof.** The 4-arm pilot was a ceiling null on one task, not "instruction cannot change outcomes" (`aio_arc_findings_and_results.md:109-111`, `:222`).
6. **Acting without retrieval.** Scoped queries can return 0 for generic queries (`retrieval_audit.md:24`, `:48-51`); a reader must know the exact scope, and most phases never retrieve (`retrieval_audit.md:52`).
7. **Over-building the loop before the bounded fix.** The wave corpus's kept direction is "keep the existing task state current after confirmed actions — the first fix, not another memory format" (`aio_arc_findings_and_results.md:190-191`).

**Open disagreements (preserved, not resolved):** loop rate — every turn vs the plant's time constant; single authority vs resilience; capacity vs compliance as the 25-hour-failure root cause; human review's value; build breadth (`aio_arc_findings_and_results.md:211-214`). Also open: the fork-vs-broad question this very evaluation exists to test (`aio_arc_findings_and_results.md:142-146`).

## (3) The single best next move — with acceptance test and cost

**Move: execute the controller's bounded item 4 — first re-verify whether the stale-next-action gap exists today, then make confirmed actions update the task/binding state, and land it with a regression test.**

Why this move (reasoning, anchored):
- It is a **controller-directed next item**, explicitly the bounded-improvement branch: "turn one useful finding into a bounded improvement using existing machinery — stale next-action state **or** a missing regression check, after verifying the gap exists today" (`aio_arc_findings_and_results.md:140-141`, `:197-198`).
- It targets the **observed** instance of the central failure class: "a binding still instructing 'activate, then submit' after both had happened" (`aio_arc_findings_and_results.md:179-180`), the same state-vs-authority gap as the swallowed restart and the false trip (`:174-177`, `:170-171`).
- It is the **kept direction** from the wave corpus: keep existing task state current after confirmed actions, "the first fix, not another memory format" (`aio_arc_findings_and_results.md:190-191`).
- It uses **existing machinery** (the versioned binding update path; the confirmed-action records) rather than a new artifact contract — respecting the no-new-framework prohibition (`:204-205`) and the build-breadth warning (`:214`).
- It is the **smallest real instance of the proposed posterior loop**: prior = the expected state; execute = the fix; posterior = diff against the confirmed outcome (`world_model_loop.md:5-28`). Proving it here de-risks the larger pilot (`world_model_loop.md:56-60`).

**Acceptance test (two gates, both mechanical):**
1. **Gap gate (prerequisite):** reproduce the stale state today — a binding/`next_action` that still instructs an action that has already been confirmed (the observed "activate, then submit" case, `aio_arc_findings_and_results.md:179-180`). If it does **not** reproduce, switch to the named alternative: add the missing regression check (e.g., for the swallowed restart / acceptance-vs-effect seam, `:174-177`, `:140-141`).
2. **Fix gate:** after a confirmed action (a durable submit or a merge), the rendered capsule/next-action no longer instructs the completed action — i.e., the state is diffed against the confirmed outcome, the arc's own lesson (`aio_arc_findings_and_results.md:77-81`). Evidence: a regression test that fails on the pre-fix tree and passes after, run through the workflow's local gates (`world_model_loop.md:43`, `:61-63`).

**Cost:** bounded local code + test work; no additional model spend. Anchors for scale: pilot cells cost `$0.006–$0.019` each (`aio_arc_findings_and_results.md:104-107`) and the synthesis rerun `$0.0315` (`contemplation_waves_1_2_review.md:127`) — this move is below both. The expensive currency here is the controller's attention (`aio_arc_findings_and_results.md:67`), which a bounded fix spends far less of than another wave.

**Named alternatives (why not now, preserved):** the **world-model-loop pilot** is the strategic follow-on but needs an artifact contract before it is executable (`world_model_loop.md:45-60`); the **local CI preflight** is the cheapest enabling move but is tactical (`world_model_loop.md:61-63`); the **Q-B differential harness** is sequenced by the controller only as recurrence-insurance after the synthesis rerun, not a review replacement (`aio_arc_findings_and_results.md:194-196`; `contemplation_waves_1_2_review.md:113-114`, `:119-125`).

## FINDING

The evidence's one repeated failure class is substituting a proxy for the authority's own output — the false trip, the swallowed restart, `queued` read as `running` (`evidence/aio_arc_findings_and_results.md:170-180`). The single best next move is the controller's bounded item 4: verify today whether a binding still instructs an already-confirmed action, then make confirmed actions update the task/binding state and add a failing-first regression test (`aio_arc_findings_and_results.md:140-141,179-180,190-191`). Acceptance: the stale instruction no longer renders after the confirmed action, test-gated; if the gap is absent, fall back to the missing regression check. Cost is bounded local code/test, below the measured $0.006–$0.019 cell and $0.0315 synthesis anchors.

## synthesis

The evidence files exist in this workspace. Reading all four:
Let me see what else this workspace carries (specs / checkout) before reconciling:
I read all four evidence files (`aio_arc_findings_and_results.md`, `contemplation_waves_1_2_review.md`, `retrieval_audit.md`, `world_model_loop.md`) and cross-checked every anchor the four sibling answers use. This is the reconciliation. Two lenses independently proposed the same move; two proposed different ones, so the disagreement is preserved rather than averaged.

---

# Reconciliation — four lens analyses of the AIO arc evidence

**Method and rationale (verbose mode).** The four siblings are four cuts of one corpus, and the corpus itself carries a known epistemic failure (an input-bounded synthesis presented as authoritative). So I treat the accepted records and the named artifacts as primary and the sisters as advisory, merge claims that repeat across lenses, verify each anchor against the file, and resolve only what a file can settle — the corpus arithmetic settles to a discrepancy; the ledger question does not settle without a checkout read. Because all four propose a "next move", I rank them rather than concatenate them.

## 1. Findings (deduplicated, grounded)

**F1 — The synthesis-input bound is the package's most consequential defect.** Wave-1's synthesis read siblings only through a 4,000-char window; wave-2's received no sibling outputs at all because its prompt never inserted `{prior_answers}` (`contemplation_waves_1_2_review.md:16-25`; `aio_arc_findings_and_results.md:11-17,126-130`). The consequence, drawn by the review itself: the two syntheses are "the least trustworthy documents in this package"; the 24 raw answers are the material (`contemplation_waves_1_2_review.md:30-31`). This invalidates only the cross-sibling *conclusions* (notably "retire further contemplation"), not the observed work.

**F2 — Delivery and emission were repaired and verified, but two gaps remain.** `run-1ec7bb0052f0` delivered 24/24 answers complete (355,473 chars) with an `answers_delivered` manifest and 24/24 read calls (`aio_arc_findings_and_results.md:153-158`; `contemplation_waves_1_2_review.md:127-134`); emission end-to-end was verified separately including mid-report retrieval and link resolution (`contemplation_waves_1_2_review.md:145-156`; `aio_arc_findings_and_results.md:159-162`). The named residual gaps: the manifest carries **no lineage labels**, and the excluded prior syntheses are cited second-hand (`contemplation_waves_1_2_review.md:132-134`). One contradiction is unresolved: `aio_arc_findings_and_results.md:227` says `final_response` "is now persisted on the ledger", while `contemplation_waves_1_2_review.md:26-29` says `PhaseResult.to_dict` omits it.

**F3 — The recurring failure pattern is "acceptance ≠ effect": a cheap adjacent quantity substituted for the authority's own output.** Instances all within one arc: the capacity false trip (a valid session refused at WARN 172,491 against 968,000 usable, `aio_arc_findings_and_results.md:170-171`), three config-resolver divergences (`:172-173`), and the swallowed `fleet_manager restart` (claimed; queue and processing lane empty; no compose call; PID unchanged) plus "a queued submit is NOT a running run" (`:174-177`). The record names the pattern but, correctly, not as a law (`:223`).

**F4 — The corpus is telemetry-heavy and the arc's analysis is not retrievable.** 54,286 records; `fact` 45,858 (85%) vs `finding` 3,908 (`retrieval_audit.md:14-18`). The query `"submission accepted versus work completed"` returns spec-index churn, not the arc's pattern (`:29-32`); scoped queries can return **0** under the exact-match pre-filter (`:23-24,49-50`); retrieval-in-the-loop is enabled by only 8 specs (`:51-52`). The emission switch was then flipped for all 20 `emit_self:false` opt-outs (`:63-66`) — and no measurement yet shows the newly emitted analysis is retrievable.

**F5 — The audit's own counts do not reconcile (reconciled here).** The category list (`retrieval_audit.md:14-16`) sums to **54,103**, not the stated 54,286; only the lifecycle figures (52,303 + 1,470 + 513) reach 54,286. A 183-record gap must be attributed (unclassified tail or transcription) before the "85% facts" baseline is quoted.

**F6 — The pilot is a ceiling null, not a disproof.** 12/12 cells accepted, no arm separated (`aio_arc_findings_and_results.md:100-111`); four grounds reject "provably ≤ 0" (`contemplation_waves_1_2_review.md:105-117`; `aio_arc_findings_and_results.md:199-205`).

**F7 — The world-model loop is `proposed`, with three missing artifacts** (world-model artifact + contract, posterior diff, runtime skill path) (`world_model_loop.md:45-55`), under an explicit "do not build a generalized prose compiler or another governance framework" (`aio_arc_findings_and_results.md:204-205`).

## 2. Risks / mistakes to avoid (ranked)

**R1 (highest) — This reconciliation can repeat the original defect.** The delivery bound is one silent truncation away, lineage labels are missing, and D1 is unresolved; a reconciliation that reads 4/4 complete inputs can still be uncheckable for *which* complete texts it received (`contemplation_waves_1_2_review.md:26-29,132-134`; `aio_arc_findings_and_results.md:227`).
**R2 — Overclaiming the ARM A/B verdict from a saturated oracle or non-quality proxies.** Binary oracles saturate (`aio_arc_findings_and_results.md:109-111,222`); overlap is not idea-diversity (`contemplation_waves_1_2_review.md:43-47`); cache-read counts are counts, not hit rates (`aio_arc_findings_and_results.md:63-67`).
**R3 — Acceptance signals that pass while substance is clipped.** `derive_phase_record` keeps a canonical + last line clipped to 200 chars; two different reports sharing a closing sentence extract identically (`contemplation_waves_1_2_review.md:136-143`).
**R4 — The emission flip floods a corpus already 85% facts and degrades retrieval** (`retrieval_audit.md:14-18,63-66`) — unmeasured.
**R5 — A scope pre-filter returning 0 reads as "nothing exists"** (`retrieval_audit.md:23-24,49-51`); the reader verb closes only the CLI side (`:57-61`).
**R6 — Leaving stale operational state.** A binding still instructed "activate, then submit" after both happened (`aio_arc_findings_and_results.md:179-180`); control actions leave no terminal receipt (`:174-176`).
**R7 — Hardening the `UCB95(−τ_g) > δ` context-dose rule on inconclusive data** (`aio_arc_findings_and_results.md:206-209`; `contemplation_waves_1_2_review.md:113-117`).
**R8 — Assuming fork identity rather than transporting it** (frozen real-session Docker forks unproven; in-process used) (`aio_arc_findings_and_results.md:218,229`).

## 3. Single best next move, with acceptance test

**Move — re-run the standing retrieval audit's four verbatim queries against the current corpus, now that the emission switches are on, and append the result to `retrieval_audit.md`.**

Why this one: the audit's own re-run trigger has fired (`retrieval_audit.md:54-55,63-66`); it is the cheapest falsifier of the package's highest-stakes live contradiction (`aio_arc_findings_and_results.md:228` "no KB emission today" vs `retrieval_audit.md:63-66`, and emission-verified at `contemplation_waves_1_2_review.md:145-156`); it is the explicit precondition for the world-model `prior` (`world_model_loop.md:13-19,34-37`); it is read-only, uses existing machinery (`knowledge read` + `--contains`), and is a **non-saturating** oracle (`aio_arc_findings_and_results.md:109-111,222`).

**Acceptance test (positive, evidence-link, provenance, and the honest negative):**
1. `agentic-dynamics knowledge read --query "submission accepted versus work completed" --scope agentic-dynamics` (plus the offline `--contains` fallback) returns a newly emitted analysis finding carrying the acceptance-vs-effect pattern — **not** the four `138 specs changed` spec-churn findings (`retrieval_audit.md:29-32`).
2. A mid-report phrase from an emitted contemplation report retrieves that report's finding and its evidence link resolves to the full text (mirrors `contemplation_waves_1_2_review.md:145-156`).
3. Provenance recorded: append the exact query strings, record ids, and the `finding` delta against the 45,858/3,908 baseline to `retrieval_audit.md` — and resolve the F5 183-record discrepancy there.
4. **Negative half:** if query 1 still returns only telemetry/spec churn, record that as the prior's top gap and **stop** — do not build the world-model loop on an unverified retrieval layer.

**Cost:** no model spend; one read-only session with existing tools. **Immediate prerequisite (near-free):** settle D1 by reading `PhaseResult.to_dict` in the checkout (`aio_arc_findings_and_results.md:227` vs `contemplation_waves_1_2_review.md:26-29`) and add **lineage labels** to the delivery manifest (`:132-134`), since this reconciliation's own standing depends on it.

**Runner-up, preserved:** the RISKS lens's delivery-proof move — persist/verify each phase's complete response plus a lineage-labeled manifest before trusting the ARM A/B verdict. **And** the NEXT-MOVES lens's bounded item 4 — verify today that a binding still instructs an already-confirmed action, then make confirmed actions advance task state with a failing-first regression test (`aio_arc_findings_and_results.md:179-180,190-191,197-198`). Neither is refused; both are sequencable after the audit.

## 4. Preserved disagreements

- **Best next move:** delivery-proof (RISKS) vs audit re-run (OPPORTUNITIES and CONTRADICTIONS, independently) vs stale-next-action bounded fix (NEXT-MOVES). Not resolved here.
- **D1 — is `final_response` persisted?** `aio_arc_findings_and_results.md:227` vs `contemplation_waves_1_2_review.md:26-29`; must be read from the checkout.
- **Emission status:** `aio_arc_findings_and_results.md:228` ("no emission today") vs `contemplation_waves_1_2_review.md:145-156` (emission verified) vs `retrieval_audit.md:63-66` (all 20 flipped, `control_room_run_journey.yaml` pending).
- **Cache:** headline percentages (`aio_arc_findings_and_results.md:61`) vs "a count, not a rate" (`:63-67`; `contemplation_waves_1_2_review.md:36-41`).
- **Harness:** "cheaper than the review" (`contemplation_waves_1_2_review.md:91`) vs "recurrence-insurance, not a review replacement" (`:113`).
- **Gap 3:** "closed" (`retrieval_audit.md:57-61`) with the scope rules unchanged vs the zero-result gap (`:23-24,49-50`).
- **"Self-contained"** (`aio_arc_findings_and_results.md:5`) vs four "not carried by this branch" markers (`:73,77,81,85`).
- **Retrieval-in-the-loop** exists / 8 specs (`world_model_loop.md:37`) vs "most phases never retrieve" (`retrieval_audit.md:51-52`).
- **Anti-framework direction** (`aio_arc_findings_and_results.md:204-205`) vs the three-artifact loop (`world_model_loop.md:45-76`) — both trace to the controller, so this is a direction collision, not agent overreach.
- **The evidence's own open set:** loop rate; single authority vs resilience; capacity vs compliance as root cause; human review's value; build breadth (`aio_arc_findings_and_results.md:211-214`).

## FINDING

The four lenses converge on one defect: the arc repeatedly accepted a proxy for the authority's own output — an input-bounded synthesis, an empty queue for a completed dispatch, an emission switch for retrieval (`aio_arc_findings_and_results.md:170-180`; `contemplation_waves_1_2_review.md:16-34`). Delivery and emission were repaired and verified once, but the ledger-persistence claim is contradicted, lineage labels are missing, and the corpus is still 85% telemetry with the arc's analysis unretrieved (`retrieval_audit.md:14-42`). The cheapest decisive next move is to re-run the standing audit's four queries now that emission is on, with a negative result that stops the world-model work. Resolve D1 against the checkout and add lineage labels before trusting any synthesis — including this one.