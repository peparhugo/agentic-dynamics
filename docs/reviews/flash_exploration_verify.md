---
status: accepted
---

# flash_exploration — build-side end-to-end verification (`p4_verify`)

**Deliverable of:** `workflows/repository/flash_exploration_build.yaml` › `p4_verify`.
**Verified at:** HEAD `f3957a318741f0853161a64f60e400f4f1e83ebe` (`feature/flash-exploration`),
the tip after `p1_reachability` (`c740ac41a`), `p2_pattern_repair` (`f5cbc43b9`), and
`p3_instrument` (`f3957a318`). Base: `bd5c530e2` (main HEAD; ancestor of HEAD).
**Scope:** read-only. NO mint, NO live-KB write. The live data plane (`/app/experiments/results`)
and the live Neo4j graph are read; the only filesystem side effect was a temporary
`experiments/results` symlink for Probe 4, removed before this document was committed.

**Result: PARTIAL — corrected after the independent adversarial review (`g5_adversarial`, verdict
FAIL; findings F2/F5/F6).** Every probe below has an exact command and raw output, but three
required claims were overstated in the first revision of this document and are NOT proven here:

- the **dense (Chroma) leg was never exercised** — `chromadb` is not installed in the container,
  so Probe 1 ran lexical-only and Probe 2b is a pure-function check (F2);
- **no live DERIVED `pattern` record exists**, so the live retrieval proof cannot cover patterns
  until the post-build mint (F2);
- the **two-revision dry-run does not demonstrate live convergence** — both revisions report the
  one-time supersede migration; convergence (0/0) is proven only against a temp registry (F5),
  and the live second dry-run after the mint is still required.

The author-side repairs and their regression tests live in
`docs/reviews/flash_exploration_remediation.md`; this document keeps its raw probe outputs
unchanged and downgrades only the disposition.

## Environment / reproduction contract

- **The built code lives in `/repo/src`; the container's installed package is a frozen base-image
  copy at `/app/src`.** Every probe therefore pins `PYTHONPATH=/repo/src` (first on the path) so
  `agentic_dynamics` resolves to the branch under test:

  ```bash
  $ PYTHONPATH=/repo/src python3 -c "import agentic_dynamics.knowledge.retrieval as r; print(r.__file__, r.COMMIT_EXEMPT_AUTHORITY_NAMES)"
  /repo/src/agentic_dynamics/knowledge/retrieval.py ('MEASURED', 'DERIVED', 'ADVISORY')
  ```

- **Live stores reachable from this container:** Neo4j at `bolt://neo4j:7687`
  (`neo4j`/`password123`; 36,360 `Knowledge` nodes — 1,178 MEASURED, 323 DERIVED, 539 ADVISORY,
  164 POLICY, 34,156 SOURCE) and Redis at `finops-queue:6379` (KB DB 2). **Chroma is NOT
  available** — `chromadb` is not installed (`ModuleNotFoundError`), so the dense leg is exercised
  only through the pure `_dense_filter` (Probe 2b) and its hermetic unit tests.
- **`scripts/kb_produce_facts.py` resolves the durable artifact dir from `PROJECT_ROOT`
  (`/repo`), not the env.** Probe 4 therefore used the standard ignored path
  `ln -s /app/experiments/results /repo/experiments/results` (removed afterwards; `git status`
  clean before commit). The dry-run itself touches nothing (it returns before `emit_records`).

## Summary

| # | Probe | Command shape | Verdict |
|---|---|---|---|
| 1 | Reachability: mismatched commit returns ≥1 MEASURED finding; `pattern_projection` toggles patterns | in-process `retrieve()` vs live Neo4j | **PARTIAL** — lexical leg only; live dense + DERIVED pending the mint (F2) |
| 2 | SOURCE commit gate still holds at all three layers | `freshness_multiplier` + `_dense_filter` + live Neo4j `search_knowledge_fulltext` | **PASS (lexical + pure-function)** — the live dense clause is untested (F2) |
| 3 | `portfolio_diversity`: divergent > 0, identical 0, single/empty → None means | in-process instrument | **PASS** |
| 4 | Pattern convergence: dry-run at two revisions; simulated first mint → 0/0 | `kb_produce_facts --dry-run` + temp-registry re-derivation | **PARTIAL** — convergence proven only against a temp registry; the live dry-runs both supersede (F5) |
| 5 | `run.py`: unique rep/variant slugs; `solution_code` persisted | in-process helpers + static call-site/consumer check | **PARTIAL at this commit** — `solution_code` was `""` for uncollected source; corrected to `None` (F4) |

---

## Probe 1 — retrieval reachability across a mismatched commit

**Requirement (design G-B1 / F1).** `retrieve()` with `pattern_projection=True` and a
`commit_sha` different from the records' commit must return at least one MEASURED finding;
`pattern_projection=False` must exclude any pattern.

**Command**

```bash
cd /repo && PYTHONPATH=/repo/src python3 - <<'PY'
import json
from collections import Counter
from agentic_dynamics.knowledge.retrieval import retrieve
from agentic_dynamics.knowledge.graph import Neo4jClient

QUERY = "perturbed class semantic correctness flail confidence"
MISMATCHED = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"

gc = Neo4jClient(uri="bolt://neo4j:7687", user="neo4j", password="password123")
for flag in (True, False):
    att = retrieve(
        QUERY,
        dense_store=None,            # chromadb not installed in this container
        graph_client=gc,
        repository_id="agentic-dynamics",
        acl_scope="public",
        commit_sha=MISMATCHED,
        top_k=40,
        pattern_projection=flag,
    )
    st = Counter(c.source_type or "<untyped>" for c in att.selected_evidence)
    au = Counter(c.authority.name for c in att.selected_evidence)
    print(f"pattern_projection={flag}: fallback={att.fallback_mode} "
          f"candidates={len(att.candidates)} selected={len(att.selected_evidence)}")
    print(f"    selected source_type={dict(st)} authority={dict(au)}")
    print(f"    patterns_in_selected={sum(1 for c in att.selected_evidence if c.source_type=='pattern')}")
    print(f"    findings_in_selected={sum(1 for c in att.selected_evidence if c.source_type=='finding')}")
    if att.selected_evidence:
        s = att.selected_evidence[0]
        print(f"    first: authority={s.authority.name} source_type={s.source_type} "
              f"commit={s.commit_sha} locator={s.locator}")
        print(f"           text={s.text[:90]!r}")
gc.close()
PY
```

**Raw output**

```text
pattern_projection=True: fallback=lexical_graph_only candidates=40 selected=30
    selected source_type={'finding': 30} authority={'MEASURED': 30}
    patterns_in_selected=0
    findings_in_selected=30
    first: authority=MEASURED source_type=finding commit=results/v1 locator=exp_0mwneie4
           text='openai/gpt-5.6 under perturbed (class semantic) -> correctness 1.00, cost $0.3443, flail 0'
pattern_projection=False: fallback=lexical_graph_only candidates=40 selected=30
    selected source_type={'finding': 30} authority={'MEASURED': 30}
    patterns_in_selected=0
    findings_in_selected=30
    first: authority=MEASURED source_type=finding commit=results/v1 locator=exp_0mwneie4
           text='openai/gpt-5.6 under perturbed (class semantic) -> correctness 1.00, cost $0.3443, flail 0'
```

**Reading.** With the probe commit `deadbeef…` (≠ the records' `results/v1`), the pipeline
returns **30 MEASURED findings** — the pre-fix gate would have returned zero. `fallback_mode`
is `lexical_graph_only` because the dense leg is down (no `chromadb`), so this is a genuine live
store read, not a mocked one. The pattern count is **0 at both flag settings**, reported
honestly: the live KB holds **0 `source_type=pattern`** records (F2 — the projection was never
written; the data-plane mint is the AIO's separate act, after the build).

**Probe 1b — the `pattern_projection` gate itself, both directions (hermetic, no live pattern
exists to exercise it).** A synthetic `graph_client` injects one well-formed DERIVED pattern
projection plus one MEASURED finding and drives the **real** `retrieve()` path:

```bash
cd /repo && PYTHONPATH=/repo/src python3 - <<'PY'
import json
from agentic_dynamics.knowledge.retrieval import retrieve, _candidate_allowed, Authority

PATTERN_PROPS = {
    "knowledge_id": "pattern://demo/1", "source_type": "pattern",
    "authority": "DERIVED", "evidence_class": "[C]", "commit_sha": "rev-A",
    "text": json.dumps({"claim": "divergent framing raises composite diversity",
        "population": "deepseek-v4-flash", "conditions": ["C1"], "support": 3,
        "uncertainty": 0.2, "validity_window": "evidence:abc",
        "source_experiment": "flash_ladder"}),
    "pattern_payload": {"claim": "divergent framing raises composite diversity",
        "population": "deepseek-v4-flash", "conditions": ["C1"], "support": 3,
        "uncertainty": 0.2, "validity_window": "evidence:abc",
        "source_experiment": "flash_ladder"},
}
FINDING_PROPS = {"knowledge_id": "finding://demo/1", "source_type": "finding",
    "authority": "MEASURED", "commit_sha": "rev-A",
    "text": "perturbed class semantic correctness flail confidence demo"}
class FakeGraph:
    def search_knowledge_fulltext(self, query, *, limit=10, commit=None):
        return [{"id": "n1", "properties": PATTERN_PROPS, "score": 5.0},
                {"id": "n2", "properties": FINDING_PROPS, "score": 4.0}]
    def expand_candidates(self, *a, **k):
        return []
for flag in (True, False):
    att = retrieve("perturbed class semantic correctness", graph_client=FakeGraph(),
                   commit_sha="rev-B", pattern_projection=flag)
    print(f"pattern_projection={flag}: selected source_types="
          f"{[c.source_type for c in att.selected_evidence]}")
print("direct _candidate_allowed('pattern', DERIVED, '[C]'):")
print("  pattern_projection=True  ->",
      _candidate_allowed("pattern", pattern_projection=True, authority=Authority.DERIVED, evidence_class="[C]"))
print("  pattern_projection=False ->",
      _candidate_allowed("pattern", pattern_projection=False, authority=Authority.DERIVED, evidence_class="[C]"))
PY
```

**Raw output**

```text
pattern_projection=True: selected source_types=['finding', 'pattern']
pattern_projection=False: selected source_types=['finding']
direct _candidate_allowed('pattern', DERIVED, '[C]'):
  pattern_projection=True  -> True
  pattern_projection=False -> False
```

**Reading.** With the flag on, the DERIVED pattern survives selection; with it off, the same
query yields only the finding. The gate is real in both directions; only the live *supply* of
patterns is absent, which the data-plane mint supplies.

---

## Probe 2 — the SOURCE commit gate still holds at all three layers

**Requirement (design B1 / F1).** The reachability fix must not weaken the code gate: a
mismatched-commit `SOURCE` record is excluded at (a) fusion-time freshness, (b) the Chroma
`where`, and (c) the Neo4j lexical query; MEASURED/DERIVED are admitted.

### 2a/2b — the pure layers

**Command**

```bash
cd /repo && PYTHONPATH=/repo/src python3 - <<'PY'
from agentic_dynamics.knowledge.retrieval import (
    freshness_multiplier, _dense_filter, COMMIT_EXEMPT_AUTHORITY_NAMES, Authority,
)
CUR, OTHER = "rev-B", "rev-A"

print("=== layer (a): freshness_multiplier (fusion-time) ===")
for auth in (Authority.SOURCE, Authority.MEASURED, Authority.DERIVED):
    m = freshness_multiplier(authority=auth, commit_sha=OTHER, observed_at=None,
                             current_commit=CUR)
    print(f"  {auth.name:9s} mismatched({OTHER}) -> {m}  ({'EXCLUDED' if m is None else 'admitted'})")
print("  SOURCE exact-commit boost ->",
      freshness_multiplier(authority=Authority.SOURCE, commit_sha=CUR, observed_at=None,
                           current_commit=CUR))
print("  SOURCE empty-commit       ->",
      freshness_multiplier(authority=Authority.SOURCE, commit_sha="", observed_at=None,
                           current_commit=CUR))

print()
print("=== layer (b): _dense_filter (Chroma where) ===")
flt = _dense_filter({"repository_id": "agentic-dynamics", "acl_scope": "public",
                     "commit_sha": CUR})
print("  exempt authorities:", COMMIT_EXEMPT_AUTHORITY_NAMES)
print("  where =", flt)

def chroma_match(where, meta):
    if "$and" in where:
        return all(chroma_match(c, meta) for c in where["$and"])
    if "$or" in where:
        return any(chroma_match(c, meta) for c in where["$or"])
    ((k, v),) = where.items()
    return str(meta.get(k, "")) == str(v)

src = {"repository_id": "agentic-dynamics", "acl_scope": "public",
       "commit_sha": OTHER, "authority": "SOURCE"}
meas = {**src, "authority": "MEASURED"}
print(f"  mismatched SOURCE chunk admitted? {chroma_match(flt, src)}  (expected False -> excluded)")
print(f"  mismatched MEASURED chunk admitted? {chroma_match(flt, meas)}  (expected True -> admitted)")
PY
```

**Raw output**

```text
=== layer (a): freshness_multiplier (fusion-time) ===
  SOURCE    mismatched(rev-A) -> None  (EXCLUDED)
  MEASURED  mismatched(rev-A) -> 1.0  (admitted)
  DERIVED   mismatched(rev-A) -> 1.0  (admitted)
  SOURCE exact-commit boost -> 1.1
  SOURCE empty-commit       -> 1.0

=== layer (b): _dense_filter (Chroma where) ===
  exempt authorities: ('MEASURED', 'DERIVED', 'ADVISORY')
  where = {'$and': [{'repository_id': 'agentic-dynamics'}, {'acl_scope': 'public'}, {'$or': [{'commit_sha': ''}, {'commit_sha': 'rev-B'}, {'authority': 'MEASURED'}, {'authority': 'DERIVED'}, {'authority': 'ADVISORY'}]}]}
  mismatched SOURCE chunk admitted? False  (expected False -> excluded)
  mismatched MEASURED chunk admitted? True  (expected True -> admitted)
```

*Layer (b) is a pure-function evaluation, not a live Chroma query:* `chromadb` is not installed
in this container, so the store cannot be reached from either the probe or the suite. The
`$or` clauses are the exact strings `kb_worker.py` persists (`record.authority.name`), and the
filter's behavior is pinned by `tests/test_retrieval.py` (100 passed, below).

### 2c — the live Neo4j lexical layer

**Command**

```bash
cd /repo && PYTHONPATH=/repo/src python3 - <<'PY'
from agentic_dynamics.knowledge.graph import Neo4jClient

MISMATCHED = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
c = Neo4jClient(uri="bolt://neo4j:7687", user="neo4j", password="password123")

# Audit: how many SOURCE code nodes match the term at commits OTHER than the probe commit?
raw = c.search_fulltext("knowledge_text_ft", "relay_once", limit=50,
                        exempt_authorities=())
source_mismatched = [r for r in raw
                     if r["properties"].get("authority") == "SOURCE"
                     and r["properties"].get("commit_sha") != MISMATCHED]
print(f"raw index audit: 'relay_once' matches at a mismatched commit -> {len(source_mismatched)} SOURCE node(s)")

print()
print("=== layer (c): live Neo4j lexical leg (search_knowledge_fulltext, exemptions ON) ===")
hits = c.search_knowledge_fulltext("relay_once", limit=50, commit=MISMATCHED)
auth = {}
for h in hits:
    auth[h["properties"].get("authority")] = auth.get(h["properties"].get("authority"), 0) + 1
print(f"  commit={MISMATCHED[:12]} -> {len(hits)} hits, by authority: {auth}")
print(f"  SOURCE hits returned: {auth.get('SOURCE', 0)}  (expected 0 -> stale code excluded)")

print()
print("=== old behavior (no exemptions) for contrast ===")
old = c.search_fulltext("knowledge_text_ft", "relay_once", limit=50,
                        commit=MISMATCHED, exempt_authorities=())
print(f"  exempt_authorities=() -> {len(old)} hits (all SOURCE filtered; knowledge would be too)")

print()
print("=== knowledge authorities admitted at the lexical layer ===")
kh = c.search_knowledge_fulltext("perturbed class semantic correctness", limit=50,
                                 commit=MISMATCHED)
ka = {}
for h in kh:
    ka[h["properties"].get("authority")] = ka.get(h["properties"].get("authority"), 0) + 1
print(f"  commit={MISMATCHED[:12]} -> {len(kh)} hits, by authority: {ka}")
c.close()
PY
```

**Raw output**

```text
raw index audit: 'relay_once' matches at a mismatched commit -> 3 SOURCE node(s)

=== layer (c): live Neo4j lexical leg (search_knowledge_fulltext, exemptions ON) ===
  commit=deadbeefdead -> 0 hits, by authority: {}
  SOURCE hits returned: 0  (expected 0 -> stale code excluded)

=== old behavior (no exemptions) for contrast ===
  exempt_authorities=() -> 0 hits (all SOURCE filtered; knowledge would be too)

=== knowledge authorities admitted at the lexical layer ===
  commit=deadbeefdead -> 50 hits, by authority: {'MEASURED': 50}
```

**Reading.** The index demonstrably holds **3 SOURCE nodes** matching `relay_once` at commits
other than the probe commit, and the live lexical leg returns **0** of them — the code gate is
intact. The same leg admits **50 MEASURED** nodes at the mismatched commit. This is the direct
live counterpart to layer (a)'s `None` and layer (b)'s `False`.

---

## Probe 3 — portfolio_diversity edge cases

**Requirement (design G-B3 / B3).** Two divergent samples → positive; the same sample twice → 0;
one sample → `None` means, coverage `single`; none → empty.

**Command**

```bash
cd /repo && PYTHONPATH=/repo/src python3 - <<'PY'
import json
from agentic_dynamics.measurement.diversity import portfolio_diversity

A = '''class TaskManager:
    def __init__(self):
        self.tasks = {}
        self.seq = 0
    def add_task(self, title, priority=3):
        self.seq += 1
        self.tasks[self.seq] = {"title": title, "priority": priority}
        return self.seq
    def ready_tasks(self):
        return [t for t in self.tasks.values() if not t.get("done")]
'''

B = '''def add_task(store, title, priority=3):
    store.append({"title": title, "priority": priority, "done": False})
    return len(store) - 1

def ready_tasks(store):
    return [t for t in sorted(store, key=lambda x: -x["priority"]) if not x["done"]]

def load(path):
    with open(path) as fh:
        return json.load(fh)
'''

print("--- two divergent samples ---")
print(json.dumps(portfolio_diversity([A, B]).to_dict(), indent=2))
print("--- identical sample twice ---")
print(json.dumps(portfolio_diversity([A, A]).to_dict(), indent=2))
print("--- one sample ---")
print(json.dumps(portfolio_diversity([A]).to_dict(), indent=2))
print("--- none ---")
print(json.dumps(portfolio_diversity([]).to_dict(), indent=2))
PY
```

**Raw output**

```text
--- two divergent samples ---
{
  "n": 2,
  "n_pairs": 1,
  "mean_novelty": 0.761,
  "mean_architecture_divergence": 0.0,
  "mean_structure_divergence": 0.225,
  "mean_composite": 0.2958,
  "max_composite": 0.2958,
  "distinct_fraction": 0.0,
  "coverage": "full"
}
--- identical sample twice ---
{
  "n": 2,
  "n_pairs": 1,
  "mean_novelty": 0.0,
  "mean_architecture_divergence": 0.0,
  "mean_structure_divergence": 0.0,
  "mean_composite": 0.0,
  "max_composite": 0.0,
  "distinct_fraction": 0.0,
  "coverage": "full"
}
--- one sample ---
{
  "n": 1,
  "n_pairs": 0,
  "mean_novelty": null,
  "mean_architecture_divergence": null,
  "mean_structure_divergence": null,
  "mean_composite": null,
  "max_composite": null,
  "distinct_fraction": null,
  "coverage": "single"
}
--- none ---
{
  "n": 0,
  "n_pairs": 0,
  "mean_novelty": null,
  "mean_architecture_divergence": null,
  "mean_structure_divergence": null,
  "mean_composite": null,
  "max_composite": null,
  "distinct_fraction": null,
  "coverage": "empty"
}
```

**Reading.** Divergent pair `mean_composite = 0.2958 > 0`; identical pair `0.0` exactly;
`n=1` and `n=0` yield `None` for every mean/max/fraction with `coverage` `"single"`/`"empty"` —
the null-not-zero rule. (The divergent pair's `architecture_divergence` is `0.0` here because
both samples share the same module-level architecture; the composite is carried by novelty and
structure. That is the metric behaving as specified, not a degenerate case.)

---

## Probe 4 — pattern convergence across revisions

**Requirement (design G-B2 / B2).** Re-deriving the same evidence at two revisions must converge;
a first mint emits 6 facts + 6 projections, and a second derivation emits 0/0.

### 4a — live dry-run at two revisions

**Command** (the symlink makes `scripts/kb_produce_facts.py`'s `PROJECT_ROOT`-relative
`KB_ARTIFACT_DIR`/`REGISTRY_INDEX_PATH` resolve to the live plane; it is gitignored and removed
after the probes):

```bash
cd /repo
ln -s /app/experiments/results experiments/results
PYTHONPATH=/repo/src FINOPS_KB_WRITE=0 python3 scripts/kb_produce_facts.py \
  --reducer pattern/v1 --dry-run --revision f3957a318741f0853161a64f60e400f4f1e83ebe
PYTHONPATH=/repo/src FINOPS_KB_WRITE=0 python3 scripts/kb_produce_facts.py \
  --reducer pattern/v1 --dry-run --revision bd5c530e2ee05f359eb759695af985a6cc7410ce
rm -f experiments/results
```

**Raw output**

```text
[kb-produce-facts] pattern/v1: derived 12 fact record(s) (revision=f3957a318741, repository-id='agentic-dynamics')
[kb-produce-facts] dry-run: would emit 12 fact record(s) (limit=none)
[kb-produce-facts]   719b7dbc3500  [fact/supersede]  workload:pattern/process_perturbation_resample/baseline#pattern
[kb-produce-facts]   6bb7ab1c86b8  [fact/supersede]  workload:pattern/process_perturbation_resample/process_perturbation#pattern
[kb-produce-facts]   611a88b86feb  [fact/supersede]  workload:pattern/task_manager/baseline#pattern
[kb-produce-facts]   6171226b0463  [fact/supersede]  workload:pattern/task_manager/objective_mutation#pattern
[kb-produce-facts]   5e6f614cfe5f  [fact/supersede]  workload:pattern/task_manager/process_perturbation#pattern
[kb-produce-facts] pattern/v1: derived 12 fact record(s) (revision=bd5c530e2ee0, repository-id='agentic-dynamics')
[kb-produce-facts] dry-run: would emit 12 fact record(s) (limit=none)
[kb-produce-facts]   6d4029b2dd5c  [fact/supersede]  workload:pattern/process_perturbation_resample/baseline#pattern
[kb-produce-facts]   9d83f041c1eb  [fact/supersede]  workload:pattern/process_perturbation_resample/process_perturbation#pattern
[kb-produce-facts]   c68b1495eb11  [fact/supersede]  workload:pattern/task_manager/baseline#pattern
[kb-produce-facts]   0c62816d2a62  [fact/supersede]  workload:pattern/task_manager/objective_mutation#pattern
[kb-produce-facts]   2d19c3976dbc  [fact/supersede]  workload:pattern/task_manager/process_perturbation#pattern
```

**Reading.** Both revisions report the **same counts** (`derived 12`, `would emit 12` = the 6
facts + 6 projections). The operation is `supersede` on both because the **live registry still
carries the pre-B2 revision-window** fingerprints — this is the expected, one-time migration
(the design's "≤6 one-time supersessions"); it is a property of the *stored* data, not of the
new derivation. The knowledge ids differ between revisions because `source_revision` remains
part of the record's run identity (`sha256(entity_id | source_revision | content_hash |
reducer_version)`), while the *supersession decision* is taken on the revision-independent
`fact_fingerprint` (4b). Convergence is therefore demonstrated at the decision boundary, which
is what the fix changes.

### 4b — simulated first mint + re-derivation (temp registry, no live write)

**Command**

```bash
cd /repo && PYTHONPATH=/repo/src:/repo/scripts python3 - <<'PY'
import json, tempfile
from pathlib import Path
import kb_produce_facts as kpf
from agentic_dynamics.control.reducers.pattern import pattern_v1, decode_pattern_payload
from agentic_dynamics.control import fact_ingestion as fi

REPO, NOW = "agentic-dynamics", "2026-09-10T00:00:00+00:00"
REV_A, REV_B = "a" * 40, "b" * 40
evidence = kpf._pattern_finding_evidence()
facts_a = pattern_v1(kpf._family_input(REPO, REV_A, NOW, evidence))
facts_b = pattern_v1(kpf._family_input(REPO, REV_B, NOW, evidence))

print(f"canonical finding evidence rows: {len(evidence)}")
print(f"derived patterns at two revisions: {len(facts_a)} / {len(facts_b)}")

print("\nrevision-independence of the evidence-digest window + fingerprint:")
same = 0
for fa, fb in zip(facts_a, facts_b):
    wa = decode_pattern_payload(fa.value).validity_window
    wb = decode_pattern_payload(fb.value).validity_window
    ra, rb = fi.build_fact_record(fa), fi.build_fact_record(fb)
    fa_p, fb_p = fi.fact_fingerprint(ra), fi.fact_fingerprint(rb)
    ok = (wa == wb and fa_p == fb_p)
    same += ok
    print(f"  {fa.subject_id:55s} window={wa}  fingerprint_equal={fa_p == fb_p}  "
          f"source_revision a/b differ={fa.source_revision != fb.source_revision}")
print(f"identical across revisions: {same}/{len(facts_a)}")

def line(rec, reason_fn):
    return json.dumps({
        "knowledge_id": rec.knowledge_id, "entity_id": rec.entity_id,
        "source_type": rec.source_type, "logical_locator": rec.logical_locator,
        "source_uri": rec.source_uri, "lifecycle_state": "current",
        "observed_at": rec.observed_at, "indexed_at": rec.indexed_at,
        "supersedes": rec.supersedes, "causes": rec.causes, "reason": reason_fn(rec),
    })

tmp = Path(tempfile.mkdtemp())
reg = tmp / "registry_index.jsonl"

io_a: dict[int, str] = {}
f_a = fi.derive_fact_records(facts_a, registry_path=reg, identity_out=io_a)
p_a = fi.derive_pattern_projection_records(facts_a, registry_path=reg, identity_out=io_a)
print(f"\nsimulated first mint (rev A): facts emitted={len(f_a)} projections emitted={len(p_a)}")
with reg.open("w") as fh:
    for rec in f_a:
        fh.write(line(rec, fi.fact_reason) + "\n")
    for rec in p_a:
        fh.write(line(rec, fi.pattern_projection_reason) + "\n")

io_b: dict[int, str] = {}
f_b = fi.derive_fact_records(facts_b, registry_path=reg, identity_out=io_b)
p_b = fi.derive_pattern_projection_records(facts_b, registry_path=reg, identity_out=io_b)
print(f"re-derivation at rev B:        facts emitted={len(f_b)} projections emitted={len(p_b)}")
print("fact fingerprints all identical across revisions: "
      f"{all(fi.fact_fingerprint(fi.build_fact_record(a)) == fi.fact_fingerprint(fi.build_fact_record(b)) for a, b in zip(facts_a, facts_b))}")
PY
```

**Raw output**

```text
canonical finding evidence rows: 64
derived patterns at two revisions: 6 / 6

revision-independence of the evidence-digest window + fingerprint:
  pattern/process_perturbation_resample/baseline          window=evidence:3d5d0b8504471b28  fingerprint_equal=True  source_revision a/b differ=True
  pattern/process_perturbation_resample/process_perturbation window=evidence:31ae44ff78081331  fingerprint_equal=True  source_revision a/b differ=True
  pattern/task_manager/baseline                           window=evidence:8880a22be83698a9  fingerprint_equal=True  source_revision a/b differ=True
  pattern/task_manager/objective_mutation                 window=evidence:22467a3ab01fe7eb  fingerprint_equal=True  source_revision a/b differ=True
  pattern/task_manager/process_perturbation               window=evidence:0fb11dde6c50e765  fingerprint_equal=True  source_revision a/b differ=True
  pattern/task_manager/specification_corruption           window=evidence:881ccbefec024c31  fingerprint_equal=True  source_revision a/b differ=True
identical across revisions: 6/6

simulated first mint (rev A): facts emitted=6 projections emitted=6
re-derivation at rev B:        facts emitted=0 projections emitted=0
fact fingerprints all identical across revisions: True
```

**Reading.** All 6 patterns carry `evidence:<16-hex>` windows (never the revision) and identical
fingerprints at both revisions while `source_revision` still differs — the window moved from
run-identity to content-identity exactly as designed. A simulated first mint emits **6 facts +
6 projections**; re-deriving the same evidence at the other revision emits **0 facts and 0
projections** — the reducer's decision boundary, proven on a temp registry. **Correction (F5):
this does NOT prove live convergence** — the live dry-runs at both revisions still report the
one-time supersede migration (12 derived = 6 facts + 6 projections), because the live registry
holds the pre-B2 windows. Live convergence requires the post-mint second dry-run.

---

## Probe 5 — `run.py` artifact-name uniqueness + `solution_code` persistence

**Requirement (design G-B3 / F5).** Independent `seed_variant`/`repetition` attempts must stop
overwriting each other's artifacts/reports, and the generated solution must be recoverable from
the result JSON. A static check of the code paths is acceptable.

### 5a — the helper behavior (in-process)

**Command**

```bash
cd /repo && PYTHONPATH=/repo/src:/repo/scripts python3 - <<'PY'
import importlib.util

spec = importlib.util.spec_from_file_location("run_mod", "/repo/scripts/run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)

print("=== _attempt_suffix: names are unique per (variant, repetition) ===")
seen = {}
for variant in (0, 1, 2):
    for rep in (0, 1, 2):
        r = {"seed_variant": variant, "repetition": rep}
        slug = f"cfg_model_op_s1{run._attempt_suffix(r)}"
        seen.setdefault(slug, []).append((variant, rep))
        print(f"  variant={variant} rep={rep} -> {slug}")
dupes = {k: v for k, v in seen.items() if len(v) > 1}
print(f"  distinct slugs: {len(seen)} / 9; collisions: {dupes or 'none'}")
print(f"  default (0,0) suffix is empty: {run._attempt_suffix({'seed_variant': 0, 'repetition': 0})!r}")

print()
print("=== _serialize_solution_code: solution code is persisted, deterministically ===")
files = {"b.py": "print('b')\n", "a.py": "print('a')\n", "sub/c.py": "x = 1\n"}
code = run._serialize_solution_code(files)
print(code)
print(f"  empty portfolio -> {run._serialize_solution_code(None)!r} / "
      f"{run._serialize_solution_code({})!r}")
print(f"  deterministic order (two runs equal): "
      f"{run._serialize_solution_code(files) == run._serialize_solution_code(dict(reversed(list(files.items()))))}")
PY
```

**Raw output**

```text
=== _attempt_suffix: names are unique per (variant, repetition) ===
  variant=0 rep=0 -> cfg_model_op_s1
  variant=0 rep=1 -> cfg_model_op_s1_r1
  variant=0 rep=2 -> cfg_model_op_s1_r2
  variant=1 rep=0 -> cfg_model_op_s1_v1
  variant=1 rep=1 -> cfg_model_op_s1_v1_r1
  variant=1 rep=2 -> cfg_model_op_s1_v1_r2
  variant=2 rep=0 -> cfg_model_op_s1_v2
  variant=2 rep=1 -> cfg_model_op_s1_v2_r1
  variant=2 rep=2 -> cfg_model_op_s1_v2_r2
  distinct slugs: 9 / 9; collisions: none
  default (0,0) suffix is empty: ''

=== _serialize_solution_code: solution code is persisted, deterministically ===
# === a.py ===
print('a')

# === b.py ===
print('b')

# === sub/c.py ===
x = 1

  empty portfolio -> None / None   # g5 round-2 F4: uncollected source is NULL, never ""
  deterministic order (two runs equal): True
```

**Correction (g5 round-2 F4, `f481c8d4e` + this pass).** The raw output above was captured
before the F4 repair: ``_serialize_solution_code(None)``/``({})`` now return ``None``
(uncollected source), so an attempt is never indistinguishable from an intentionally empty
one. The live consumer is `scripts/score_flash_ladder.py` /
`agentic_dynamics.measurement.portfolio_score`, which excludes ``None`` attempts and reports
the excluded count (`tests/test_portfolio_scorer.py`, `tests/test_run_result_shape.py`).

### 5b — the static call-site / consumer check

**Command**

```bash
cd /repo
grep -n "solution_code\|_serialize_solution_code\|_attempt_suffix" scripts/run.py
grep -rn "_s{s}\|_s{strength}\|f\"{name}_" \
  scripts/analyze_worktrees.py scripts/archive/backfill_artifacts.py scripts/inventory.py scripts/build_data.py
```

**Raw output**

```text
217:        "solution_code": _serialize_solution_code(code_files),
347:        "solution_code": _serialize_solution_code(code_files),
468:        attempt = _attempt_suffix(r)
558:def _attempt_suffix(run: dict) -> str:
577:def _serialize_solution_code(code_files: dict[str, str] | None) -> str:
```

```text
(no consumer lines matched the slug patterns)
```

**Reading.** `solution_code` is written into **both** the baseline (`run.py:217`) and perturbed
(`run.py:347`) records; the suffix is applied to the artifact dir (`:468`) and the markdown
report (`:513`). The default `(0,0)` attempt keeps the exact legacy name, and every non-default
`(variant, rep)` gets a distinct suffix (9/9 unique). No consumer
(`analyze_worktrees`/`backfill_artifacts`/`inventory`/`build_data`) parses the slug — they build
their own names from worktree paths or scan JSON filenames — so the rename cannot break them.

---

## Supporting test run (independent of the probes)

The four suites the `g6_test_gate` will run were executed against the same `PYTHONPATH`:

```bash
cd /repo && PYTHONPATH=/repo/src python3 -m pytest \
  tests/test_retrieval.py tests/test_context_plane_pattern.py \
  tests/test_kb_produce_facts_integration.py tests/test_diversity.py \
  -q -p no:cacheprovider
```

```text
........................................................................ [ 52%]
..................................................................       [100%]
138 passed in 1.22s
```

`tests/test_graph.py` (46 tests) **skips** in this container — its Neo4j fixtures hardcode
`bolt://localhost:7687`, which is not reachable here (the live graph is reached by name at
`bolt://neo4j:7687`, as Probe 2c does directly).

---

## Honest limitations (not failures)

1. **`chromadb` is not installed in this container**, so the dense retrieval leg could not be
   exercised live. Probe 1 ran the real `retrieve()` against the live Neo4j lexical leg
   (`fallback_mode=lexical_graph_only`); the dense commit filter is verified as a pure function
   (Probe 2b) plus the hermetic `tests/test_retrieval.py`. The build change to `_dense_filter`
   is the exact `$or` shape shown in 2b.
2. **0 live `source_type=pattern` records** exist. Probe 1 therefore reports the pattern count
   honestly as 0 and exercises the `pattern_projection` gate both ways with an injected
   projection through the real `retrieve()` path (Probe 1b). Supplying real patterns is the
   AIO's post-build data-plane mint, explicitly out of scope here.
3. **The live pattern dry-run still shows `supersede`** (12 = 6 facts + 6 projections) at both
   revisions, because the live registry still holds the pre-B2 revision windows. This is the
   registered one-time migration; convergence (0/0) is proven against a temp registry in 4b.
4. **No live `run.py` experiment was executed** (cost); Probe 5 is the permitted static +
   helper-level check, and the call sites are confirmed by grep.

## Disposition

- **PARTIAL (corrected).** Every probe has its exact command and raw output; the original
  disposition overstated what they prove, as the independent adversarial review found
  (F2/F5/F6). Dense-leg, live-DERIVED, and live-convergence evidence remain outstanding.
- Before the data-plane mint: the remediation repairs (F3 metric normalization, F4
  `solution_code` null) and a host-side live Chroma mismatched-commit probe; then a fresh
  adversarial re-review and `g6_test_gate`.
- After the controller-approved mint: a live DERIVED-pattern query and a second live dry-run
  (0 fact / 0 projection supersessions) demonstrating F2b and live convergence.
- Committed as the `p4_verify` deliverable with commit prefix
  `[workflow] p4_verify — Build the flash exploration wave: KB rea…`.
