---
status: accepted
---

# Control Room Facelift: Second Adversarial Pass

**Date:** 2026-09-13. **Verdict: REWORK.** The first wave is not executable exactly as
specified. Park automatic question-tree execution, not the bounded UI work, until its missing
runtime contracts are implemented or consistently removed from the claims.

Frontmatter marks this as a recorded review under the repository's lifecycle convention; it does
not accept a1/a2 for execution or authorize permanence.

**Reviewer:** OpenAI `openai/gpt-6-astra`, independently assessing the revised artifacts.
Pass 1 identifies itself as a stand-in without a second-model selector, but does not identify
its actual model family (`docs/reviews/control_room_facelift_adversarial.md:9-17`). Independence
of this assessment is stated; different-family provenance cannot be verified from that artifact.

**Method and limits.** Read-only document audit plus delegated, read-only source inspection.
No browser, model experiment, deployment, or product test was run. Source observations below
are not fresh rendering results. The requested control preflight, `agentic-dynamics control
status --json`, failed because the command is unavailable; this is an environment gap, not an
empty control packet. No control action was taken. Only this review is written; a1/a2 and all
other inputs remain unchanged. Session work closes with this review; runtime verification is
explicitly not claimed.

**Citation key:** `P` = `docs/website/control_room_ui/facelift_task_plan.md`;
`D` = `docs/website/control_room_ui/dynamic_workflow_design.md`;
`A` = `docs/reviews/control_room_facelift_adversarial.md`;
`R` = `docs/research/control_room_direction.md`;
`S` = `docs/research/control_room_ui_reference_synthesis_v2.md`.
Numbers following these aliases are source line numbers, not review line numbers.

## 1. Disposition Audit

This audits **corrections to a plan**, not whether future implementation already exists.
**Present** means the claimed textual correction is there; **partial/nominal** means a missing
edge, unbound acceptance, or contradictory capability claim prevents closure; **deferred** means
the limitation is explicit, not implemented. Finding IDs V2-01 through V2-12 below supply the
required corrections and falsifiers.

### Task-plan dispositions

Every row of P:380-405 is covered, including the design cross-reference W-6.

| Disposition | Audit | Correction actually present, or evidence it is nominal |
|---|---|---|
| D-1 | Partial | P:206 narrows attention to packet values; P:207 parks the independent supervisor axis. The visual/timestamp claim exceeds the named tests (V2-03). |
| D-2 | Present, dependency gap | Literal `unknown` and cost-unknown fixture are stated at P:189,249. F13 does not require their F03 producer; fixture execution must not be assumed (V2-04/05). |
| D-3 | Present | F24 is `structure`, P:270. |
| D-4 | Partial | F10 names a mutation-boundary test and F24 a client spy, P:226,270. Neither is a precise gate-of-record target; F10 still leaves the operational door unspecified (V2-05/06). |
| D-5 | Partial | All seven tasks are in the wave, P:292; F11 depends on both B tasks, P:242. Entry/exit circularity survives (V2-01/02). |
| T-1 | Partial | Scorecard and consumer have owners, P:187-188; F02a still accepts on the class-B check F02b creates (V2-02). |
| T-2 | Partial | Split exists, P:185-196. Detector work still requires unexplained product-green before later UI repair (V2-01). |
| T-3 | Nominal completion | P:389 claims completion through T-11; F06 still has no F04 prerequisite path, P:209 (V2-04). |
| T-4 | Present | F25a first in wave two, F25b after it, P:276-277,348. |
| T-5 | Present ownership split | Repo F26a and controller-owned host F26b are separate, P:283-284. Host-success acceptance is still missing (V2-06). |
| T-6 | Partial | Visible-text/clip checks are explicit, P:242,249. Detector positive-control conflict and fixture-only truth remain (V2-01/03). |
| T-7 | Present labels | F24 is `[P]/[X]`, F26a/b `[M]`, P:270,283-284. These classify proposed checks, not measured success. |
| W-6 | Partial | Hard filter exists in D:190-198; existing compiler enforcement and dependency examples still do not establish it (V2-07/11). |
| D-6 | Partial | Packet-only rendering and parked F27 are explicit, P:206-207,250. Claimed schema enforcement at P:409-412 is absent from the current validator; timestamps and update paths remain unspecified (V2-03). |
| D-7 | Present/deferred | Partial/history-capped, merged/published and six-state cases are at P:189,243,249; disagreement precedence is blocked on D8, P:434. Fixture allocation and dependency closure remain defective (V2-04/06). |
| D-8 | Present split, partial gate | F25a/b and browser contrast are named, P:276-277. Blind A/B evidence still lacks candidate binding and a concrete scoring target (V2-02/05). |
| D-9 | Mostly present | Brain/Herdr re-anchors and authored map exist at P:267-270. P:65-70 wrongly points to dispositions in §8 instead of §7; P:88 locates both fleet gates in `model_policy.py`, although F26a correctly names `spawn_wrapper.py`. |
| T-8 | Present gate correction | Full browser gate, missing detector and exit-2 block are explicit, P:185-186,315. Exit 1 alone does not prove the intended detector fired (V2-01). |
| T-9 | Present in P only | F01a precedes F01b, P:186,327. D still advertises Q11a/Q11b as parallel gate holes, D:148 (V2-04/11). |
| T-10 | Partial | Human-only score and split exist, P:187-188,432. The record can precede the screen it certifies and still needs its later reader (V2-02). |
| T-11 | Nominal | P:402 says all five edges were added; F06's row at P:209 omits F04. F08's table edge exists at P:224 but is absent from the displayed F04 edge list, P:332 (V2-04). |
| T-12 | Present root cause, partial proof | F26a fixes whitelist membership, P:283. F26b accepts a remaining blocker rather than successful container resolution, P:284 (V2-06). |
| T-13 | Deferred | Typed door, receipt and non-steering contract are at P:208; default parked at P:427. Enabling an ack does not by itself waive R:682-685's route-class restriction. |
| T-14 | Nominal adjudication | P:230-242 repeats the instruction to re-adjudicate **before scheduling**, but schedules F11 without that adjudication. It also says to correct the repair verdict when nothing is missing, which does not follow (V2-03). |

**Revision note audit, P:65-72.** All three named splits exist: F02a/b at P:187-188,
F25a/b at P:276-277, F26a/b at P:283-284. F01 serialization exists. Removal of client
derivation exists as a task commitment, not a demonstrated invariant. The claimed five completed
consumer edges, universal observable gates, and guaranteed small leaves do not hold, as shown
above. The references to §8 for dispositions and rejected sub-demands should be §7.

**Rejected sub-demands.** Rejecting mandatory live capture (P:409-412) is defensible because
deterministic real-projection fixtures can prove the same contract; claiming an enum schema already
does so is not. Deferring disagreement precedence because the truth table is read-only
(P:413-416) is defensible, but only that fixture should block, not the unrelated F03 bundle.

### Dynamic-design dispositions

Every row of D:499-514 is covered, including the duplicate W-1 row and D-9.

| Disposition | Audit | Correction actually present, or evidence it is nominal |
|---|---|---|
| W-1 mechanism surface | Partial | Authored default and auto-gen gap exist, D:302-334. Default transport is still falsely attributed to story workers, D:483-485 (V2-07). |
| W-2 | Partial | Gate uncertainty is explicitly binary, D:227-232. D:299-300 again assigns a posterior to every open question; real estimator/mapping gaps remain (V2-08). |
| W-3 | Present distinction | Authored paid phase versus absent per-node hook is explicit, D:364-371. Cost closure is separately invalid under W-14. |
| W-4 | Partial | Weighted sum is replaced, D:200-209. Lexicographic composition, missing signals and mixed candidate arbitration have no binding contract (V2-08). |
| W-5 | Partial | Advisory-only policy and ledger-only default are stated, D:290-298. Current emission API/defaults cannot enforce those statements without additional specified changes (V2-10). |
| W-6 | Partial | Hard filter present, D:190-198. Compiler declarations are still confused with completed-question evidence, D:138-139,479-480 (V2-07). |
| W-7 | Nominal guarantee | D:316-318 states campaign allocation and once-only matched settlement; D:332 simultaneously defers campaign allocation. Shared scope is not allocation/accounting (V2-09). |
| W-8 | Partial | Phase timeout is correctly separated from StopSpec, D:248-257. Inactivity watchdog is still promoted to campaign-deadline/frontier enforcement, D:447 (V2-09). |
| W-1 auto-gen | Deferred | D:334,532 leave it controller-authored by default. This is a valid deferral, not an executor closure. |
| W-9 | Partial | Missing bridge is named and sized L, D:332. Authored `phases:` still supposedly unlock existing workers, D:483-485 (V2-07). |
| W-10 | Partial | Synthetic falsifier is no longer empty by construction, D:240-244. It tests invented candidate values, not a working question/evidence mapping (V2-08). |
| W-11 | Partial | Equivalence withdrawal and non-owning Q1 wording exist, D:384-393. Coverage is only promised at D:443; examples still mis-schedule dependencies and duplicate F20 (V2-11). |
| W-12 | Partial | Attempt is defined as a gate rerun, D:258. Immediate unchanged-red exclusion conflicts with parking after N reruns; changing reds/child expansion can evade the bound (V2-09/11). |
| W-13 | Partial | Recorder is a prerequisite, D:282-289. Authority/causes and missing-field suppression need more than populating `PhaseResult` (V2-10). |
| W-14 | Nominal cost bound | D:369-371,539 call an agent phase one model call and assert budget enumeration. The workflow has an aggregate cap, not that per-phase allocation (V2-12). |
| D-9 in a2 | Present anchors | Q1 now cites direction §4.2; Q14 cites decorative pulse, D:393,407. Rejecting a blanket v2-only pin demand, D:518-521, is reasonable. |

**Revision-note cross-check.** D:216-244 corrects the missing Question-to-RuleResult mapping
only locally; D:299-300 and §9 reintroduce the unimplemented guarantees. D:322-345 is not a
complete honest-gap list: question readiness/identity, coverage ownership, acceptance evidence
binding, mixed selection, retry/expansion state and campaign deadline enforcement are absent.
D:333 also names `control/phase_evidence.py`, although its own D:289 correctly names
`runtime/phase_evidence.py`. D:464's "authority now explicit" describes a proposal, not current code.

### Where Pass 1's Closures or Remedies Are Rejected

These are disagreements with the prior reasoning, not merely demands for implementation.

| Pass-1 item | Disagreement |
|---|---|
| T-10 remedy, A:63 | A human pass created before F07/F11 cannot certify their later output. Split schema/reader infrastructure from a final-candidate human checkpoint (V2-02). |
| T-9 acceptance, A:62 | Serializing dependent edits is sufficient; requiring both patch orders to work contradicts that remedy. Require ordered integration and both independent detector tests, not reverse-order applicability. |
| D-6 capture demand, A:50 | Runtime capture is neither necessary nor sufficient for schema coverage. Use deterministic producer-backed packets and intentionally marked contradictions (V2-03). |
| T-14 remedy, A:67 | If the field is already present, remove duplicate work; do not change a correct historical repair verdict merely because it is present now. Correct a verdict only against evidence from the scope it actually judged. |
| W-11 remedy, A:77 | An explicitly illustrative tree need not emit the authored first wave. It must still respect dependencies, and any executable tree needs a separate complete ownership manifest (V2-11). |
| W-14 remedy, A:80 | One agent phase is not one inference call. The revision copied an invalid cost unit from pass 1 (V2-12). |
| T-11 compiler proof, A:64 | `validate_rules` checking declared outputs cannot prove runtime readiness of UI work items (V2-07). |

## 2. Required Corrections, Severity Ranked

### V2-01 [High]: Bootstrap Gates Require Their Own Outputs

**Evidence.** P:311-320 says the wave does not **start** until rendering and the human
scorecard pass; P:187-188 creates that scorecard and its consumer inside the wave. F01a
also requires F-0 product-green while adding the detector (P:185), but mobile CSS deliberately
clips row labels to 1x1px (`apps/control_room/static/style.css:1200-1210`), which F11 later
promises to eliminate (P:242). Detector-only scope cannot guarantee product-green.

**Correction.** Separate environment entry checks, detector sensitivity checks and final product
exit gates. Test the detector against isolated good/bad controls; inventory existing product failures
for bounded UI repairs rather than exempting selectors to preserve green. Give required-visible
carriers an explicit contract so legitimate assistive-only text is not indiscriminately rejected.

**Acceptance.** F01a can start with no scorecard and known baseline product failures; wave exit
cannot pass with either missing final evidence or those failures. Individually seed duplicate,
overflow, clipped and occluded required carriers; each fails its intended diagnostic. A valid visible
control and a legitimate screen-reader-only control pass. Do not accept an unrelated exit 1 as proof.

### V2-02 [High]: Human Evidence Is Neither Candidate-Bound Nor Acyclic

**Evidence.** F02a requires failure of the class-B check that F02b creates (P:187-188).
F11 considers comprehension satisfied once those earlier tasks are green (P:242). Neither
names screenshot/candidate identity, timing, comparator results or carrier identification.
R:439-458 requires both desktop/mobile captures, ten seconds, no hover/selection, and the
generic comparator; this is stronger than five booleans plus schema validity.

**Correction.** F02a owns schema and scoring protocol with example records; F02b owns the reader.
Final screenshots require a separate human checkpoint after F04/F07/F11, and again after a restyle
that changes their carriers. Bind records to capture hashes, rendered-content identity, viewports,
fixture, protocol and assessor observations. Human availability is an explicit block, not an S/M
agent-session guarantee. Apply the same evidence binding to F25b.

**Acceptance.** Missing, stale, wrong-candidate, wrong-viewport, over-time or hover-dependent
records fail; all five sentences and all seven glance answers have correct identified carriers and
the required comparator outcome. Altering final pixels invalidates the old pass. Schema examples
cannot be mistaken for human approval. This breaks both the task-reader cycle and evidence reuse.

### V2-03 [High]: First-wave State/Row Truth Can Pass on Fictional Fixtures

**Evidence.** F04's static suite has no JS runtime
(`tests/test_control_room_static_views.py:1-9,92-97`). It cannot observe glyphs, timestamps,
forced colors or transitions. `_run_row` emits no per-axis changed-at timestamp and no row
budget fields (`apps/control_room/routes/glance.py:548-575`), while F-0 supplies six budget
fields (`apps/control_room/verification/fixtures/F-0.json:47-52`). The validator does not enforce
the claimed attention enum (`scripts/verify_control_room_rendering.py:288-318`). Missing
attention defaults to `none`, and legacy transitions derive it from lifecycle
(`apps/control_room/static/app.js:300-303,814-827`).

F11's baseline is also unadjudicated. The reserved/cap band already exists
(`app.js:383-398`); G-13 already compares `spec.cell`
(`scripts/verify_control_room_rendering.py:2169-2175`). Actual residuals include mobile basename
substitution (`app.js:320-327`), desktop-only source/authority (`app.js:351-374`), and hidden
lease metadata (`app.js:383-394`). A fixture rich in unproduced data can make UI-only work look live.

**Correction.** Before sizing F04/F11, list exact producer fields and residual selectors. Require
honest unknowns for absent data, or separately scope a projection change. Do not invent transition
timestamps from poll time. Use deterministic real-projection packets, with adversarial contradictions
explicitly marked. Cover all update paths, not just the initial renderer. Keep F27's independent
supervisor-axis deferral distinct from claimed direction compliance.

**Acceptance.** Missing/unsupported attention renders `unknown`; changing emitted attention while
lifecycle stays fixed changes only that axis. Legacy events cannot derive attention. Timestamp
absence stays unknown; no-op updates neither reset it nor write DOM. Browser tests verify shape,
word and visible value at all three breakpoints, forced colors and reduced motion. Known/unavailable
budget cases come through a named producer; hidden titles/attributes cannot satisfy visible-text
acceptance. Final-candidate human checks certify the remaining F11 repairs.

### V2-04 [High]: Dependency Tables Do Not Describe One Executable Graph

**Evidence.** F06 lacks F04 (P:209 versus P:402). P:328 omits F01b -> F02a, required by
P:187. P:332 omits F04 -> F08, required by P:224. The displayed graph omits F06 -> F23
(P:269). F19 consumes F03's oversized fixture without a dependency (P:189,260), and F13
accepts new partiality/unknown cases without an F03 path (P:249). D:133-148 still advertises
parallel questions whose task equivalents share prerequisites and files.

**Correction.** Make one dependency manifest authoritative, including fixture producers, decisions,
gate infrastructure and write-conflict constraints; derive the diagram. Dependencies must gate
integration of state consumers, not merely promise eventual common vocabulary. Either migrate all
shared update paths atomically or specify what remains unchanged until each later consumer lands.

**Acceptance.** A deterministic dependency audit rejects the current missing edges and table/diagram
drift. F06/F08 cannot run before F04; fixture consumers cannot pass before their fixtures exist and
execute. The first wave has closed prerequisites without importing all D8-blocked work. Shared-file
tasks are integrated in a declared order and final no-regression checks cover legacy paths.

### V2-05 [High]: Green Gate Names Do Not Prove Their Task Questions

**Evidence.** P:131-152 declares an exclusive gate list. It has no scorecard schema/class-B reader
entry or explicit JS/client-spy targets. F07 promises linked counts but accepts ON-G1/ON-G6,
class-name absence and geometry (P:218). Existing ON-G6 accepts legal counts without comparing
all of them to truth (`scripts/verify_control_room_rendering.py:2115-2132`). A renamed KPI tile
also defeats `no .kpi/.stat-tile`. The default browser invocation runs F-0, not every future forcing
fixture (`scripts/verify_control_room_rendering.py:1442-1525,2284,2313`).

**Correction.** Register each new check with an exact target, owning task, fixture matrix and
observable assertion. Name a single aggregate target where a task needs several constituent checks;
do not disguise multiple unspecified checks as one acceptance. Include click/keyboard filter tests
in F07 or state its prerequisite contract with F08. Use structural/comprehension evidence, not CSS
class spelling, for the no-KPI claim.

**Acceptance.** Removing any promised R0 provenance carrier, changing any truth value to another
legal value, disconnecting a count link, or renaming a forbidden tile cannot stay green. Every
first-wave claim maps to an executed check in the report. Report candidate, fixtures, viewport/theme
matrix, executed classes and blocked checks; unexecuted classes never appear as passed.

### V2-06 [Medium]: Later Leaves Hide Blockers or Have No Success Condition

**Evidence.** F03 packs many scenarios into F-8 through F-12 and includes a D8-blocked scenario
(P:189); R:894-898 already assigns F-8/F-9 worker/timing roles. Unknown fixture names fall back
to seed data (`scripts/verify_control_room_rendering.py:203-206,283-285`). F10 bundles flood,
pause, grants and a service confirm path (P:226), but the cited parity suite is inventory/endpoint
coverage, not mutation-boundary proof (`tests/test_control_room_parity.py:1-16`). F19 leaves its
measured size threshold unnamed (P:260 versus S:280). F26b's acceptance merely reports a host
blocker (P:284), which cannot prove a successful mount.

**Correction.** Allocate fixtures canonically and split the D8-dependent leaf. Separate F10's
display work from any unavailable pause/grant producer and governed mutation, naming the existing
door or parking the mechanism. Define F19's local threshold/budget rather than importing Langfuse's
numbers. Give F26b a non-spending post-mount resolution probe; keep blocked distinct from success.

**Acceptance.** Unknown fixture IDs fail, every scenario has a unique intended assertion, and D8
does not block unrelated stale/oversize work. Authority tests cover absent/stale authorization,
confirmation, idempotency and unchanged pending approvals; external reference behavior is not a
local producer. Oversize tests measure bounded work and marked partiality. After the controller's
mount, a container-scoped config probe resolves the provider/model without an inference call.

### V2-07 [High]: Authored Phases Do Not Supply the Missing Executor or Readiness Gate

**Evidence.** D:302-315 acknowledges no spec-to-job bridge, then D:483-485 says existing workers
drain authored phases. They launch `run_story.py` with story-matrix arguments
(`scripts/worker.py:463-476`); authored phases execute through the workflow runner
(`src/agentic_dynamics/runtime/workflow_runner.py:3696-3699`). D:336 also claims the experiment
CLI drives it without specifying the missing connection. D:138-139,479-480 attributes runtime
question readiness to `validate_rules`, which unions **declared** measurement outputs before
checking requirements (`src/agentic_dynamics/experiment/experiment_spec.py:941-952`).

**Correction.** State the executable default as controller-authored workflow phases, not story-worker
dispatch or an executed compiler DAG. Classify the ranker as proposed and name its invocation.
Question IDs, output field IDs, acceptance evidence and dependency cycles need a separate explicit
readiness contract; existing RuleSpec validation is structural, not proof of completed work.

**Acceptance.** A zero-model authored-phase replay uses the documented workflow runner. A declared
producer with no green acceptance cannot unblock a question even when `validate_rules` passes.
Remove all claims of queued child-spec execution until a separate zero-model compile/dispatch/
worker/lineage test exists. No new scheduler is implicitly authorized by this review.

### V2-08 [High]: The Information-gain Drive Still Has No Measured Inputs

**Evidence.** D:216-232 admits the mapping gap, while D:238-239,299-300 assumes question-level
posterior, regret and effect. `RuleResult.uncertainty` defaults to zero; built-in measured evaluators
do not compute the asserted posterior (`src/agentic_dynamics/experiment/compile_experiment.py:340,
354-362,441-451,484-489`). `compare_arms` returns arm-level comparison data, not a question effect
statistic (`compile_experiment.py:308-315`). One `AdaptSpec.selection` value is validated
(`experiment_spec.py:1094-1097`), not the proposed composite selection policy.

**Correction.** For this facelift, use readiness plus a concrete authored priority. If instrumented
selection remains in scope, add estimator, Question-to-rule/arm attribution, missing-signal behavior,
strategy composition and mixed gate/instrumented arbitration to the honest-gap list. Synthetic
numbers can test sorting but cannot establish their measurement provenance.

**Acceptance.** Real evaluator outputs, no-evidence cases and missing regret/effect cannot become
fabricated certainty. A mixed candidate set has a deterministic documented order. Unsupported
measurement selection refuses or explicitly falls back; no generic zero default triggers convergence.

### V2-09 [High]: Campaign Accounting and Brakes Are Promises Without State

**Evidence.** D:254-258,316-320 promises campaign spend allocation, deadline parking and once-only
`matched` settlement. Admission reserves fresh phase leases against a shared campaign scope
(`src/agentic_dynamics/control/admission.py:838-858`), not child allocations from a parent lease.
Caps come through CLI/registry configuration (`scripts/run_workflow.py:319-347`). Settlement is
opt-in and computes a status rather than guaranteeing `matched` (`control/admission.py:741-762`;
`control/settlement.py:362-383`, under `src/agentic_dynamics/`). The workflow watchdog is inactivity
based (`runtime/workflow_runner.py:1352-1378`), not a campaign deadline. D:258 both excludes an
unchanged red and retries it until N; D:329's ranker signature has no time/deadline input.

**Correction.** Mark parent allocation, cumulative spend and campaign deadlines as deferred unless
their enforcement and recording are explicitly scoped. Separate phase timeout, inactivity timeout
and campaign deadline. Define initial attempt counting, unchanged-red identity, total-attempt cap,
restart persistence, reset rules and terminal reasons. Respect subscription-window versus dollar
units. Controller approval is not an accounting implementation.

**Acceptance.** Fake-clock/restart tests reject post-deadline admission; sequential and concurrent
children cannot exceed cumulative budget or double-count settlement. Missing meter data remains
unsettled/unknown. Unchanged and changing red results terminate after the declared total bound;
budget exhaustion, blocked frontier and successful convergence remain distinguishable outcomes.

### V2-10 [High]: Advisory Emission Requires an API Change, Not Just a Recorder

**Evidence.** D:290-298 promises explicit ADVISORY/causes and no emission without recorded fields.
The producer accepts neither override (`src/agentic_dynamics/knowledge/knowledge_ingestion.py:
505-512,575-582`), derives MEASURED from either boolean test result (`:538-540`), and falls back to
`final_response` (`:485-496`). The runner enables self-emission by default at the inspected seam
(`src/agentic_dynamics/runtime/workflow_runner.py:1226-1260`). Populating `conclusion` alone
does not enforce suppression, causal attribution or authority.

**Correction.** Enumerate an explicit question classification/derivation path, authority binding,
resolvable cause propagation and suppression default in §4.1. Mark them proposed. Preserve ordinary
measured findings separately; do not relabel every result advisory to make the test green.

**Acceptance.** Through the real runner-to-producer seam, question results with `True`, `False` and
`None` test outcomes remain advisory with valid causes; absent structured question fields cannot
bypass suppression through narrative fallback. Ordinary measured findings retain their authority.

### V2-11 [Medium]: Killing Children Can Satisfy Parents; Coverage Is Unowned

**Evidence.** D:105-116 defines parent outputs as a conjunction but leaves the parent open only
until children are green **or killed**. Killing a required producer does not produce its output.
D:234-236 assumes expansion converges, although new child IDs can evade per-question attempts;
"strictly more concrete" at D:439 is no computable bound. D:319-320 closes the tree on `None`
without a blocked/failed distinction. Coverage at D:443 only rejects duplicate **sole** carriers;
F20 is mapped by Q10 and Q16 (D:402,409). D:414-417's illustrative fan-out also violates actual
F07 -> F11, F07/F08 -> F09 and F16 -> F17 dependencies.

**Correction.** Define parent aggregation and blocked-descendant propagation; killed required
outputs cannot count as answered. Bound total expansion/attempts across lineage, not just each new
ID. Add a complete task ownership manifest with non-owning references and parked leaves distinct
from executable owners. An illustration may omit tasks but cannot teach invalid readiness.

**Acceptance.** Kill one required child and verify no dependent receives its output. Alternating
child creation/kill or changed-red results cannot evade the global bound. Missing owners and duplicate
owners inside multi-task mappings fail. A blocked-only frontier reports blocked, not converged.

### V2-12 [Medium]: An Adversary Phase Is Not One Model Call

**Evidence.** D:369-371,539 and A:80 use one call per adversary phase. The workflow declares an
agent phase and an aggregate stop cap (`workflows/repository/control_room_facelift_review.yaml:
127-130,179`); an agent can emit multiple usage-bearing step completions and tool calls
(`src/agentic_dynamics/adapters/opencode.py:1134-1172`). Enumerating phase names is not a
spend estimate or admission binding.

**Correction.** Budget one **agent phase execution**, including inference turns, tools and retries,
using a named estimate/bound and measured settlement with unknown-cost handling. Identify which
actual admission cap enforces it; do not claim StopSpec lists per-phase costs when it does not.

**Acceptance.** A stubbed multi-turn adversary attributes all usage to its admitted phase/campaign;
retries and additional adversary phases consume additional budget. Unknown usage cannot become zero.

## 3. First-wave Executability Matrix

This separates a gate that is missing from §1.3 from a registered gate that is merely too weak.

| Task | Executable exactly as specified? | Gate-of-record audit and possible false green | Required closure |
|---|---|---|---|
| F01a | No | Full browser gate is registered. F-0 positive control conflicts with new clipping rejection; grouped mutations can fail for only one reason. | V2-01; isolate each seeded diagnostic and separate detector/product exit scopes. |
| F01b | Conditional, not yet exact | Full/semantics gate registered. Its named bad cases omit some promised row/unknown checks; no explicit fixture invocation or positive control. Default F-0 does not execute a new fixture set automatically. | V2-01/05; name matrix/target and individually mutate every promised field, preserving valid zero and explicit unknown cases. |
| F02a | No | Schema/class-B record validation has **no entry** in §1.3. Its acceptance invokes the later reader and depends on an unbounded human checkpoint. | V2-02/05; schema/protocol infrastructure first, final scoring separately. |
| F02b | No | Full gate registered, but new class-B reader has **no explicit gate-of-record entry/target**. A seeded miss proves parsing, not final comprehension. | V2-02/05; register reader and require capture-bound human evidence at wave exit. |
| F04 | No | Static-view gate registered; unknown-enum and client-spy tests have **no named target/entry**. Source-presence green cannot prove visual axes or all update paths. | V2-03/05; producer map, JS/browser checks, timestamp unknowns; resize beyond S or split after inventory. |
| F07 | No | Full render gate is registered; no-tile/no-scroll assertions are described but count navigation is ungated. Incorrect legal values or dead links can pass. | V2-05; exact truth/provenance and click/keyboard lens tests, no class-name-only composition check. |
| F11 | No | G-13/full clip checks registered; mobile human proof is inherited from earlier tasks instead of final captures. Current-source scope and budget producer unresolved. | V2-02/03; adjudicate landed versus residual work, scope projection separately, final capture-bound score. |

**One-session assessment.** F01b and F02b are plausible bounded implementation leaves after their
contracts are fixed. F01a must not secretly include every exposed UI repair. F02a cannot guarantee
a human's availability. F04's initial/SSE authority and browser tests exceed the described static-map
half-session unless split. F07 is plausibly one session once navigation and field sources are fixed.
F11 cannot be sized until the residual/projection inventory is supplied. S/M labels alone prove none
of these bounds (P:94-101,114).

**Safe ordering of the revised proposal:** environment/baseline preflight; detector and semantics
infrastructure; scorecard schema/reader infrastructure; state/update-path repair; R0; adjudicated
row repair; final captures and human scoring; complete rendering/parity/regression wave exit.
This is an acceptance correction, not authorization to run or deploy the wave.

## 4. Verdict and Highest-value Corrections

**REWORK.** V2-01 through V2-05 block first-wave execution or make green acceptance unreliable.
V2-07 through V2-10 block accepting the dynamic design as an executable mechanism. V2-06,
V2-11 and V2-12 are required before scheduling their affected work or claiming convergence/cost
safety. Automatic child execution remains parked; authored UI work need not wait for that machinery.

1. **Repair the acceptance lifecycle:** split entry from exit, use independent detector controls,
   and bind human comprehension to final captures (V2-01/02/05). Proof: bootstrap runs without
   future artifacts, but stale human evidence and seeded behavior removal cannot pass wave exit.
2. **Make one producer/dependency/gate contract authoritative:** adjudicate F04/F11 against live
   projection capabilities, close missing edges, and register exact executed tests (V2-03/04/05).
   Proof: missing fields become unknown, missing prerequisites block, and each claimed carrier has
   an individually failing mutation test on the actual update paths.
3. **Remove fictional runtime guarantees:** bound the design to authored workflow execution and
   authored priority, explicitly scoping all remaining readiness, emission, accounting and stopping
   gaps (V2-07 through V2-12). Proof: one zero-model replay follows the documented runner and
   distinguishes blocked/failed/parked from converged without inventing signals or free work.
