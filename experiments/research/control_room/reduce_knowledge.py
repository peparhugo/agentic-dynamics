#!/usr/bin/env python3
"""Regenerate the Control Room catalogs + skills from the repaired taxonomy.

Companion to ``build_taxonomy.py``. It re-points every r4 catalog item and skill
record at the repaired taxonomy nodes, recomputes support/family counts from the
corpus, and downgrades any recommendation whose backing node was deleted or fell
below the >=3-source bar to an explicit ``[P]`` local design policy with a one-line
reason (never a finding). It also re-copies exact corpus titles so citation metadata
stops drifting (r6a E8).

Inputs:  corpus/*.jsonl, taxonomy.json, the committed catalogs.json/skills.json.
Outputs: catalogs.json, skills.json (rewritten in place).
Run:     python3 experiments/research/control_room/reduce_knowledge.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CORPUS_DIR = HERE / "corpus"
TAXONOMY_PATH = HERE / "taxonomy.json"
CATALOGS_PATH = HERE / "catalogs.json"
SKILLS_PATH = HERE / "skills.json"
FAMILIES = ["agentops", "dashboards", "dataviz", "cli", "craft"]
MIN_SUPPORT = 3

# Old taxonomy id -> repaired taxonomy id. ``None`` means the node was deleted by
# the repair (no source record states the technique).
RENAME: dict[str, str | None] = {
    "tech-viz-virtualized-table": "tech-viz-data-table",
    "tech-viz-heatmap-status-grid": "tech-viz-heatmap",
    "tech-viz-timeline-gantt": "tech-viz-waterfall-timeline",
    "tech-viz-sampling-decimation": "tech-viz-rendering-performance",
    "tech-ia-board-per-domain": "tech-ia-dashboard-layout",
    # deleted by the repair — see taxonomy.repair.deleted_nodes
    "tech-trust-source-provenance": None,
    "tech-trust-degraded-banner": None,
    "tech-trust-uncertainty-encoding": None,
    "tech-money-budget-thresholds": None,
    "tech-money-quota-wallet": None,
    "tech-trust-audit-trail": None,
    "tech-trust-freshness-indicator": None,
    "tech-viz-gauge": "thin-viz-gauge",
    "tech-viz-small-multiples": "thin-viz-small-multiples",
    "tech-svg-flow-diagram": "thin-svg-flow-diagram",
    "tech-int-confirmation-door": "thin-int-confirmation-door",
    "tech-ops-self-host": "thin-ops-self-host",
}

# Catalog items that split into a still-supported item + an explicit [P] item, or
# that must change id/label because the repaired backing node changed meaning.
# key: old item id -> spec for the replacement item list.
CATALOG_ITEM_OVERRIDES: dict[str, list[dict]] = {
    "ia-board-per-domain": [
        {
            "id": "ia-dashboard-layout",
            "label": "Dashboard board / grid layout",
            "recommendation": "Use a dashboard board/grid as the primary layout: the "
            "corpus' dashboards are board-and-grid surfaces, and the widget catalog they "
            "contain is catalogs.ia-widget-catalog.",
            "when": "An operator console that aggregates multiple live surfaces.",
            "avoid_when": "A single-object workflow that needs no aggregation.",
            "backing": ["tech-ia-dashboard-layout", "tech-ia-widget-catalog"],
            "evidence_class": "[X]",
        },
        {
            "id": "ia-board-per-domain",
            "label": "[P] Domain-split boards (work / money / health / decisions)",
            "recommendation": "Split the board into operator domains (work, money, health, "
            "decisions). No corpus record states this split; adopt it as local policy "
            "because r0 M1-M5 measured that the current room splits those answers.",
            "when": "The room serves multiple operator questions whose failure modes differ.",
            "avoid_when": "A single-domain console.",
            "backing": [],
            "evidence_class": "[P]",
            "policy_reason": "No source states board-per-domain partitioning; support was "
            "inflated from generic dashboards labels in r3.",
        },
    ],
    "ia-money-grouping": [
        {
            "id": "ia-money-grouping",
            "label": "[P] Money board grouping (spend / burn / quota / leases)",
            "recommendation": "Treat money as its own board grouping provider windows, "
            "wallet, leases and budget thresholds. The corpus states cost tracking only; "
            "the quota/wallet/threshold composition is local policy driven by r0 M1.",
            "when": "The operator must see spend against a hard cap.",
            "avoid_when": "Cost is someone else's concern.",
            "backing": ["tech-money-cost-attribution"],
            "evidence_class": "[P]",
            "policy_reason": "No source states quota/wallet/budget thresholds; those nodes "
            "were promoted from payments/alerting labels in r3.",
        },
        {
            "id": "money-cost-attribution",
            "label": "Cost attribution to runs/agents",
            "recommendation": "Attribute cost to the run/agent that incurred it; the "
            "agent-ops sources document cost tracking as a first-class run field.",
            "when": "Multiple agents/models spend against shared budgets.",
            "avoid_when": "Cost is fixed or untracked.",
            "backing": ["tech-money-cost-attribution", "tech-money-billing"],
            "evidence_class": "[X]",
        },
    ],
    "fw-no-build": [
        {
            "id": "fw-no-build",
            "label": "Build-less vanilla JS + CSS custom properties",
            "recommendation": "Keep the console build-less: vanilla JS state/render + CSS "
            "custom properties for tokens, and hand-authored SVG/CSS micro-visuals. The "
            "corpus' no-framework chart (uPlot) and SVG/CSS craft sources demonstrate the "
            "approach at this scale. The choice itself is a [P] local guardrail (r0 §9.8); "
            "the corpus shows viable alternatives, not proof React is unnecessary.",
            "when": "A single-page local operator console with no npm pipeline.",
            "avoid_when": "Many contributors needing a typed component model.",
            "backing": ["stk-vanilla-js", "stk-svg-css-only", "tech-svg-theme-aware-svg"],
            "evidence_class": "[X]",
            "policy_notes": [
                "[P] No-build / React-unnecessary: r0 §9.8 is the local guardrail; the "
                "corpus establishes viable vanilla/SVG options, not necessity (r6a E7).",
            ],
        }
    ],
    "ch-gauge": [
        {
            "id": "ch-gauge",
            "label": "[P] Gauge mark for a bounded quantity",
            "recommendation": "Use a gauge/radial for a single bounded quantity (queue "
            "depth, phase completion). Only one source record states a gauge; adopt as "
            "local policy where the operator question demands a bounded reading.",
            "when": "A bounded numerator against a known limit.",
            "avoid_when": "Comparing groups or showing a trend.",
            "backing": [],
            "evidence_class": "[P]",
            "policy_reason": "Direct gauge support is 1 record (craft), below the "
            ">=3-source bar; r3 reported 25 by allocating process-monitor/progress labels.",
        },
    ],
    "ch-small-multiples": [
        {
            "id": "ch-small-multiples",
            "label": "[P] Small multiples for cross-group comparison",
            "recommendation": "Use small multiples when many groups must be compared on one "
            "scale. Direct support is 2 records; adopt as local policy only where the "
            "operator question demands comparison.",
            "when": "Same measure across many groups.",
            "avoid_when": "A single series or a status overview.",
            "backing": ["thin-viz-small-multiples"],
            "evidence_class": "[P]",
            "policy_reason": "Direct small-multiples support is 2 records, below the "
            ">=3-source bar.",
        },
    ],
    "ch-table": [
        {
            "id": "ch-table",
            "label": "Sortable data table for large sets",
            "recommendation": "Use a sortable data table for large sets. The table surface "
            "is well-supported; row virtualization specifically is local policy (only 3 "
            "records state virtualized-table).",
            "when": "Many rows the operator must scan/sort/filter.",
            "avoid_when": "A handful of records better shown as cards.",
            "backing": ["tech-viz-data-table"],
            "evidence_class": "[X]",
            "policy_notes": [
                "[P] Virtualized rendering for large tables: direct virtualized-table "
                "support is 3 records (craft only).",
            ],
        },
    ],
    "tr-provenance": [
        {
            "id": "tr-provenance",
            "label": "[P] Provenance badge on consequential numbers",
            "recommendation": "Attach a provenance badge (measured / estimated / unknown + "
            "model/window) to consequential numbers. No source states source-provenance; "
            "adopt the repository's own cost-provenance vocabulary as local policy.",
            "when": "A number drives an operator decision.",
            "avoid_when": "The number is self-evident or non-consequential.",
            "backing": [],
            "evidence_class": "[P]",
            "policy_reason": "No source states provenance; r3 promoted it from "
            "logs/metrics/cost-tracking labels. Grounded in the repo's cost_provenance contract.",
        },
    ],
    "tr-freshness": [
        {
            "id": "tr-freshness",
            "label": "[P] Freshness / retained-window marker",
            "recommendation": "Show a freshness/staleness marker instead of implying live. "
            "Direct support is 1 record (staleness-threshold); local policy grounded in the "
            "repo's projection-watermark contract.",
            "when": "Any surface can lag its source.",
            "avoid_when": "The value is computed synchronously.",
            "backing": [],
            "evidence_class": "[P]",
            "policy_reason": "Direct freshness support is 1 record, below the >=3-source bar.",
        },
    ],
    "tr-degraded": [
        {
            "id": "tr-degraded",
            "label": "[P] Degraded banner naming the failing dependency",
            "recommendation": "Show a degraded banner that names the failing dependency. No "
            "source states this; adopt as local policy because r0 M-series found "
            "green-but-stale surfaces.",
            "when": "A dependency can fail independently.",
            "avoid_when": "A single source of truth with no partial failure mode.",
            "backing": [],
            "evidence_class": "[P]",
            "policy_reason": "No source states a degraded banner; r3 promoted it from the "
            "generic status label.",
        },
    ],
    "tr-uncertainty": [
        {
            "id": "tr-uncertainty",
            "label": "[P] Explicit uncertainty / unmeasured encoding",
            "recommendation": "Encode uncertainty and 'unmeasured' explicitly so a green "
            "badge never lies. No source states this; local policy grounded in the repo's "
            "cost-provenance 'unknown' class.",
            "when": "A metric can be partial or absent.",
            "avoid_when": "Every value is measured and complete.",
            "backing": [],
            "evidence_class": "[P]",
            "policy_reason": "No source states uncertainty encoding; r3 promoted it from "
            "eval/chart labels.",
        },
    ],
    "ia-audit-trail": [
        {
            "id": "ia-audit-trail",
            "label": "[P] Actor audit trail",
            "recommendation": "Keep a who-did-what-when audit trail of operator actions. No "
            "source states an audit trail; local policy for a governed approval flow.",
            "when": "Humans approve/promote/retire runs.",
            "avoid_when": "A read-only observability view.",
            "backing": [],
            "evidence_class": "[P]",
            "policy_reason": "No source states an audit trail; r3 promoted it from "
            "changelog/deployments labels, which describe a release feed.",
        },
    ],
    "svg-flow": [
        {
            "id": "svg-flow",
            "label": "[P] Flow-diagram topology",
            "recommendation": "Use a path tracer for genuine flow/route lines. The layout "
            "topology is not evidenced (2 records); adopt the specific topology as local "
            "policy.",
            "when": "A route/flow must be shown.",
            "avoid_when": "A static structural diagram suffices.",
            "backing": ["thin-svg-flow-diagram"],
            "evidence_class": "[P]",
            "policy_reason": "Direct flow-diagram support is 2 records, below the "
            ">=3-source bar; the path-tracer craft itself is supported.",
        },
    ],
    # --- E5: replace universal/superlative wording with source-bounded wording ---
    "fw-echarts": [
        {
            "id": "fw-echarts",
            "label": "ECharts for streaming + a broad chart catalog",
            "recommendation": "ECharts couples a broad chart catalog with responsive "
            "containers and documents ARIA support in its accessibility guide; the cited "
            "ECharts records state this, not a comparative ranking.",
            "when": "Many chart types and a built-in streaming renderer are needed.",
            "avoid_when": "A single mark on a build-less page.",
            "backing": ["tech-viz-chart-grammar"],
            "evidence_class": "[X]",
        }
    ],
    "ch-timeline": [
        {
            "id": "ch-timeline",
            "label": "Timeline / waterfall for runs and phases",
            "recommendation": "Use a timeline/waterfall to show a run's phases and spans "
            "over time; the cited agent-ops sources document a trace waterfall for exactly "
            "this question (single family: agentops).",
            "when": "A multi-step run must be read phase by phase.",
            "avoid_when": "A single instantaneous value.",
            "backing": ["tech-viz-waterfall-timeline"],
            "evidence_class": "[X]",
        }
    ],
    "tr-lineage": [
        {
            "id": "tr-lineage",
            "label": "Session -> trace -> span lineage",
            "recommendation": "Represent a run as a session->trace->span tree with parent "
            "links so a failure's cause is walkable; the cited agent-ops sources document "
            "this structure.",
            "when": "A failure's cause must be traced through a run.",
            "avoid_when": "Flat fire-and-forget tasks.",
            "backing": ["tech-trust-causal-lineage", "tech-ops-trace-tree"],
            "evidence_class": "[X]",
        }
    ],
    "ao-eval": [
        {
            "id": "ao-eval",
            "label": "Evaluation loop with datasets and scorers",
            "recommendation": "Treat evals as a first-class surface (datasets -> runs -> "
            "scores -> compare) alongside live traces; the agent-ops sources document the "
            "eval loop (single family: agentops).",
            "when": "Prompt/model changes must be compared before shipping.",
            "avoid_when": "No offline comparison is needed.",
            "backing": ["tech-ops-eval-loop"],
            "evidence_class": "[X]",
        }
    ],
    "ia-attention-surface": [
        {
            "id": "ia-attention-surface",
            "label": "Attention surface for alerts and health",
            "recommendation": "Give alerts and health a first-class board (severity, "
            "owner, ack), not just a count; the cited Grafana/Datadog/Sentry records "
            "separate the attention surface from the dashboard.",
            "when": "More than a handful of alerts can fire.",
            "avoid_when": "A single-threshold system with no routing.",
            "backing": ["tech-trust-alerting"],
            "evidence_class": "[X]",
        }
    ],
}

# Per-skill [P] moves that lose their source backing, with a one-line reason each.
SKILL_POLICY: dict[str, list[dict]] = {
    "skill-delivery": [
        {"move": "Stay build-less / rule out React",
         "reason": "No-build is a [P] local guardrail (r0 §9.8); the corpus shows "
                   "viable vanilla/SVG alternatives, not proof React is unnecessary."},
    ],
    "skill-shell-ia": [
        {"move": "Domain-split boards (work / money / health / decisions)",
         "reason": "No source states domain partitioning; support was inflated from "
                   "generic dashboards labels (r6a E2)."},
        {"move": "Money board grouping (quota / wallet / leases)",
         "reason": "No source states quota/wallet; support was inflated from "
                   "payments/alerting labels (r6a E3)."},
        {"move": "Alerts on a dedicated attention board",
         "reason": "Alerting as a surface is supported; the board placement is [P]."},
    ],
    "skill-glance": [
        {"move": "Status grid as the glance default",
         "reason": "Direct heatmap/status-grid support is 4 records; keep as the default "
                   "only as [P] pending a controlled comparison."},
        {"move": "Money (spend/burn/quota/leases) above the fold",
         "reason": "Cost tracking is supported; quota/lease composition is [P] (r6a E3)."},
        {"move": "Named degraded/staleness summary",
         "reason": "No source states a degraded banner or uncertainty encoding (r6a E4); "
                   "grounded in the repo's projection/cost contracts."},
    ],
    "skill-charts": [
        {"move": "Gauge for bounded quantities", "reason": "Direct gauge support is 1 record."},
        {"move": "Small multiples for cross-group comparison",
         "reason": "Direct support is 2 records."},
        {"move": "Virtualized table implementation",
         "reason": "Direct virtualized-table support is 3 records; the general table "
                   "surface is supported."},
    ],
    "skill-svg": [
        {"move": "Specific flow-diagram topology",
         "reason": "Direct flow-diagram support is 2 records; the path-tracer craft is "
                   "supported."},
    ],
    "skill-trust": [
        {"move": "Provenance badge (measured/estimated/unknown)", "reason": "No source "
         "states provenance (r6a E4); grounded in the repo's cost_provenance contract."},
        {"move": "Named degraded banner", "reason": "No source states it (r6a E4)."},
        {"move": "Explicit uncertainty / unmeasured encoding",
         "reason": "No source states it (r6a E4)."},
        {"move": "Freshness / retained-window marker",
         "reason": "Direct support is 1 record."},
    ],
    "skill-agent-ops": [],
    "skill-visual-system": [],
    "skill-synthesis": [
        {"move": "Domain-split boards", "reason": "No source states domain partitioning "
         "(r6a E2)."},
        {"move": "Gauge mark", "reason": "Direct gauge support is 1 record (r6a E1)."},
        {"move": "Status grid default", "reason": "Direct support is 4 records (r6a E1)."},
        {"move": "Money/quota/wallet grouping", "reason": "No source states quota/wallet "
         "(r6a E3)."},
        {"move": "Provenance badge / degraded banner / uncertainty", "reason": "No source "
         "states them (r6a E4)."},
        {"move": "No-build / rule out React", "reason": "[P] local guardrail (r6a E7)."},
    ],
}


def load_corpus() -> list[dict]:
    records = []
    for family in FAMILIES:
        for line in (CORPUS_DIR / f"{family}.jsonl").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            records.append(
                {
                    "family": family,
                    "uri": raw["uri"],
                    "sha": raw["sha256"],
                    "sha16": raw["sha256"][:16],
                    "title": raw.get("title", ""),
                    "techniques": set(raw.get("techniques", [])),
                }
            )
    return records


def load_taxonomy() -> tuple[dict, dict]:
    tax = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in tax["nodes"]}
    return tax, nodes


def matched_for(node_id: str, crosswalk: dict, records: list[dict]) -> list[dict]:
    """Corpus records whose direct labels back ``node_id``."""
    labels = set(crosswalk.get(node_id, []))
    if not labels:
        return []
    return [r for r in records if r["techniques"] & labels]


def node_evidence(node_id: str, nodes: dict) -> dict | None:
    node = nodes.get(node_id)
    if node is None:
        return None
    return {
        "id": node_id,
        "support": node["support"],
        "family_names": sorted(node["support_by_family"].keys()),
        "meets_three_source_rule": node["meets_three_source_rule"],
    }


def build_evidence(backing: list[str], tax: dict, nodes: dict, records: list[dict],
                   max_refs: int = 6) -> dict:
    """Recompute a catalog item's evidence block from repaired taxonomy nodes."""
    cw = tax["crosswalk"]
    node_rows = [node_evidence(b, nodes) for b in backing if b in nodes]
    node_rows = [r for r in node_rows if r is not None]
    support = max((r["support"] for r in node_rows), default=0)
    families: set[str] = set()
    for r in node_rows:
        families.update(r["family_names"])

    # Refs: round-robin across backing nodes, dedup by sha, exact corpus titles.
    seen: set[str] = set()
    refs: list[dict] = []
    pools = [matched_for(b, cw, records) for b in backing]
    pools = [p for p in pools if p]
    idx = 0
    while len(refs) < max_refs and pools:
        progressed = False
        for pool in pools:
            if idx < len(pool) and len(refs) < max_refs:
                r = pool[idx]
                if r["sha"] not in seen:
                    seen.add(r["sha"])
                    refs.append(
                        {
                            "family": r["family"],
                            "uri": r["uri"],
                            "sha256": r["sha16"],
                            "title": r["title"],  # exact corpus title (fixes r6a E8)
                        }
                    )
                progressed = True
        if not progressed:
            break
        idx += 1

    # Report the family split of the strongest backing node (transparent, not summed).
    top_id = max(node_rows, key=lambda r: r["support"])["id"] if node_rows else None
    support_by_family = nodes[top_id]["support_by_family"] if top_id else {}
    return {
        "support": support,
        "support_by_family": support_by_family,
        "independent_families": len(families),
        "taxonomy_nodes": node_rows,
        "refs": refs,
    }


def repair_catalogs(tax: dict, nodes: dict, records: list[dict]) -> dict:
    old = json.loads(CATALOGS_PATH.read_text(encoding="utf-8"))
    catalogs = []
    dropped = []

    for cat in old["catalogs"]:
        items = []
        for item in cat["items"]:
            # Items with an explicit repair override are replaced wholesale.
            if item["id"] in CATALOG_ITEM_OVERRIDES:
                for spec in CATALOG_ITEM_OVERRIDES[item["id"]]:
                    items.append(_build_catalog_item(item, spec, tax, nodes, records))
                continue
            # Default path: re-point the old backing nodes through RENAME.
            old_nodes = [n["id"] for n in item.get("evidence", {}).get("taxonomy_nodes", [])]
            new_backing = []
            for nid in old_nodes:
                mapped = RENAME.get(nid, nid)
                if mapped is not None and mapped not in new_backing:
                    new_backing.append(mapped)
            promoted = [b for b in new_backing if nodes.get(b, {}).get("meets_three_source_rule")]
            if promoted:
                new_item = dict(item)
                new_item["evidence"] = build_evidence(promoted, tax, nodes, records)
                new_item["evidence_class"] = "[X]"
                items.append(new_item)
            else:
                # Lost its source support -> explicit [P] local policy, never a finding.
                policy = dict(item)
                policy["label"] = f"[P] {item['label']}"
                policy["evidence_class"] = "[P]"
                policy["policy_reason"] = (
                    "Backing taxonomy node(s) "
                    + ", ".join(new_backing or old_nodes)
                    + " fall below the >=3-source bar after the support repair."
                )
                policy["evidence"] = {
                    "support": max(
                        (nodes[b]["support"] for b in new_backing if b in nodes), default=0
                    ),
                    "support_by_family": {},
                    "independent_families": 0,
                    "taxonomy_nodes": [
                        node_evidence(b, nodes) for b in new_backing if b in nodes
                    ],
                    "refs": [],
                }
                items.append(policy)
                dropped.append(
                    {"catalog": cat["id"], "item": item["id"],
                     "reason": policy["policy_reason"]}
                )
        catalogs.append({**cat, "items": items})

    out = dict(old)
    out["phase"] = "p0_repair_taxonomy"
    out["method"] = (
        "Catalogs re-pointed at the repaired taxonomy. Items whose backing nodes were "
        "deleted or dropped below the >=3-source bar are explicit [P] local design "
        "policies with a reason; every ref is re-derived from corpus with exact titles."
    )
    out["catalogs"] = catalogs
    # Refresh the taxonomy thin-leaf ledger from the repaired supports, then append
    # the catalog items that lost their backing.
    taxonomy_dropped = [
        {
            "catalog": "(taxonomy)",
            "item": n["id"],
            "support": n["support"],
            "reason": "thin cluster below the >=3-source bar; not promoted",
        }
        for n in tax["nodes"]
        if n["kind"] == "thin"
    ]
    out["dropped"] = taxonomy_dropped + dropped
    # Refresh the taxonomy input hash so the artifact records what it derived from.
    out["inputs"] = _inputs_with_taxonomy(old.get("inputs", []), tax)
    return out


def _build_catalog_item(old_item: dict, spec: dict, tax: dict, nodes: dict,
                        records: list[dict]) -> dict:
    """Build one catalog item from an override spec, recomputing all evidence."""
    evidence = build_evidence(spec.get("backing", []), tax, nodes, records)
    item = {
        "id": spec["id"],
        "label": spec["label"],
        "recommendation": spec["recommendation"],
        "when": spec.get("when", old_item.get("when", "")),
        "avoid_when": spec.get("avoid_when", old_item.get("avoid_when", "")),
        "evidence_class": spec["evidence_class"],
        "evidence": evidence,
        "confidence": old_item.get("confidence", "medium"),
        "caveats": old_item.get("caveats", []),
        "needs": old_item.get("needs", []),
    }
    if spec.get("policy_reason"):
        item["policy_reason"] = spec["policy_reason"]
    if spec.get("policy_notes"):
        item["policy_notes"] = spec["policy_notes"]
    return item


def repair_skills(tax: dict, nodes: dict, records: list[dict]) -> dict:
    old = json.loads(SKILLS_PATH.read_text(encoding="utf-8"))
    skills = []
    for skill in old["skills"]:
        new_skill = dict(skill)
        old_backing = [n["id"] for n in skill.get("evidence", {}).get("backing_nodes", [])]
        new_backing = []
        for nid in old_backing:
            mapped = RENAME.get(nid, nid)
            if mapped is not None and mapped not in new_backing:
                new_backing.append(mapped)
        promoted = [b for b in new_backing if nodes.get(b, {}).get("meets_three_source_rule")]
        evidence = build_evidence(promoted, tax, nodes, records, max_refs=8)
        new_skill["evidence"] = {
            "support_max": evidence["support"],
            "distinct_families": sorted({f for b in promoted for f in nodes[b]["support_by_family"]}),
            "backing_nodes": [node_evidence(b, nodes) for b in promoted],
            "refs": evidence["refs"],
        }
        policies = SKILL_POLICY.get(skill["id"], [])
        new_skill["evidence_class"] = "[P]" if policies and not promoted else "[X]"
        if policies:
            new_skill["policy"] = policies
            # Make the reclassification explicit in the prose: unsupported moves are
            # local [P] policy, never presented as corpus findings.
            new_skill["recommendation"] = skill["recommendation"] + " Local [P] policy " \
                "(not corpus findings): " + "; ".join(
                    f"{p['move']} — {p['reason']}" for p in policies
                ) + "."
        skills.append(new_skill)

    out = dict(old)
    out["phase"] = "p0_repair_taxonomy"
    out["method"] = (
        "Skills re-pointed at the repaired taxonomy. Moves that lost their source "
        "support are carried in the skill's `policy` list as [P] local design policy "
        "with a one-line reason; nothing unsupported is presented as a finding."
    )
    out["skills"] = skills
    out["inputs"] = _inputs_with_taxonomy(old.get("inputs", []), tax)
    return out


def _inputs_with_taxonomy(inputs: list[dict], tax: dict) -> list[dict]:
    """Replace the taxonomy entry with the current taxonomy hash."""
    payload = TAXONOMY_PATH.read_bytes()
    refreshed = [i for i in inputs if not i["path"].endswith("taxonomy.json")]
    refreshed.append(
        {
            "path": str(TAXONOMY_PATH.relative_to(ROOT)),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    )
    # Keep the corpus inputs first, taxonomy last (stable, readable).
    corpus = [i for i in refreshed if "corpus" in i["path"]]
    other = [i for i in refreshed if "corpus" not in i["path"]]
    return corpus + other


def validate_refs(path: Path, records: list[dict]) -> int:
    """Assert every emitted sha256/uri triple resolves to a corpus record."""
    known = {r["sha16"]: r for r in records}
    bad = 0
    payload = json.loads(path.read_text(encoding="utf-8"))

    def walk(obj):
        nonlocal bad
        if isinstance(obj, dict):
            sha = obj.get("sha256")
            if isinstance(sha, str) and len(sha) == 16:
                rec = known.get(sha)
                if rec is None:
                    bad += 1
                    print(f"  UNRESOLVED {path.name}: {obj.get('uri')} {sha}")
                elif obj.get("uri") != rec["uri"]:
                    bad += 1
                    print(f"  URI MISMATCH {path.name}: {obj.get('uri')} != {rec['uri']}")
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(payload)
    return bad


def main() -> None:
    records = load_corpus()
    tax, nodes = load_taxonomy()
    catalogs = repair_catalogs(tax, nodes, records)
    skills = repair_skills(tax, nodes, records)
    CATALOGS_PATH.write_text(json.dumps(catalogs, indent=2) + "\n", encoding="utf-8")
    SKILLS_PATH.write_text(json.dumps(skills, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {CATALOGS_PATH.name}, {SKILLS_PATH.name}")
    bad = validate_refs(CATALOGS_PATH, records) + validate_refs(SKILLS_PATH, records)
    n_policy = sum(
        1 for c in catalogs["catalogs"] for i in c["items"] if i.get("evidence_class") == "[P]"
    )
    print(f"  [P] catalog items: {n_policy}  skills with policy: "
          f"{sum(1 for s in skills['skills'] if s.get('policy'))}")
    print(f"  unresolved refs: {bad}")
    if bad:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
