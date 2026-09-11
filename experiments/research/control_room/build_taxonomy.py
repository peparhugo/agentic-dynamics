#!/usr/bin/env python3
"""Deterministic rebuild of the Control Room research taxonomy — ZERO label promotion.

Why this file exists
--------------------
Phase ``r3_taxonomy`` crosswalked the 270 raw technique labels in the five family
corpora to canonical leaves by *interpreting* broad umbrella labels
(``chart-types``, ``status``, ``metrics``, ``logs``, ``alerting``, ``dashboards``,
``payments``) as evidence for narrow techniques (``gauge``, ``heatmap-status-grid``,
``board-per-domain``, ``budget-thresholds``, ``quota-wallet``, ``degraded-banner``,
``source-provenance``). No source record states those narrow techniques, so the
resulting ``support`` counts were inflated, and r4/r5 then cited them as measured
external evidence (adversary r6a findings E1–E4).

The repair has to be reproducible and auditable, so the crosswalk and the support
computation live in code rather than in a model prompt. The rule this file enforces:

    A technique node's ``support`` is the number of DISTINCT corpus records whose own
    ``techniques`` labels directly name that node's technique. A broad label backs a
    broad umbrella node, never a narrower leaf. Labels with no direct home stay
    unmapped; nodes that existed only by promotion are deleted and listed in the
    ``repair`` block.

Run:
    python3 experiments/research/control_room/build_taxonomy.py
"""

from __future__ import annotations

import collections
import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths and constants
# --------------------------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]  # experiments/research/control_room -> repo root
CORPUS_DIR = HERE / "corpus"
TAXONOMY_PATH = HERE / "taxonomy.json"

FAMILIES = ["agentops", "dashboards", "dataviz", "cli", "craft"]
MIN_SUPPORT = 3  # the r1 §3.3 ">= 3 independent sources" bar
MAX_EXAMPLES = 12  # example refs stored per node (readability, not a support cap)

# --------------------------------------------------------------------------- #
# The direct crosswalk: canonical node -> the raw technique labels that name it.
#
# This is the heart of the repair. Only literal (morphologically trivial) labels are
# allowed. If you cannot point at the raw label and say "that label IS this
# technique", the label does not belong here.
# --------------------------------------------------------------------------- #
TECH_GROUPS: list[tuple[str, str, list[tuple[str, list[str], str]]]] = [
    (
        "grp-ia-layout",
        "IA / navigation & layout",
        [
            (
                "tech-ia-dashboard-layout",
                ["dashboards", "dashboard", "dashboard-grid"],
                "A dashboard board/grid. Sources state dashboards; none states the "
                "work/money/health/decisions domain split (that is a [P] local move).",
            ),
            (
                "tech-ia-widget-catalog",
                [
                    "widget-catalog",
                    "widgets",
                    "panel-library",
                    "dashboard-blocks",
                    "dashboard-components",
                    "blocks",
                    "tui-components",
                    "panels",
                ],
                "A named catalog/library of panels or widgets.",
            ),
            (
                "tech-ia-command-palette",
                ["command-palette", "fuzzy-find", "fuzzy-filter", "aliases"],
                "A single keystroke-summoned command/find surface.",
            ),
            (
                "tech-ia-tab-bar",
                [
                    "tabs",
                    "native-tabs",
                    "tab-bar",
                    "split-panes",
                    "panes",
                    "splits",
                    "multiplexing",
                ],
                "Tabs / split panes as the navigation unit.",
            ),
            (
                "tech-ia-progressive-disclosure",
                ["progressive-disclosure"],
                "Reveal detail on demand.",
            ),
            (
                "tech-ia-master-detail",
                ["master-detail", "docked-detail"],
                "A list/detail split with a docked detail pane.",
            ),
            (
                "tech-ia-density-ladder",
                ["density-ladder", "density", "responsive-layout", "responsive-sizing"],
                "A persisted density / responsive-layout control.",
            ),
        ],
    ),
    (
        "grp-data-viz",
        "Data / viz marks",
        [
            (
                "tech-viz-chart-types",
                ["chart-types", "charts"],
                "The broad 'this source discusses chart types' umbrella. Backs no "
                "specific mark; kept whole, never split into narrow leaves.",
            ),
            (
                "tech-viz-chart-grammar",
                [
                    "grammar-of-graphics",
                    "chart-selection",
                    "mark-based",
                    "mark-types",
                    "encoding-channels",
                    "axis-scales",
                    "data-mapping",
                    "scales",
                    "chart-craft",
                    "chart-critique",
                    "chart-description",
                    "decision-tree",
                    "defaults",
                ],
                "Grammar / encoding / mark-selection craft.",
            ),
            (
                "tech-viz-time-series-marks",
                ["line-chart", "area-chart", "bar-chart", "time-series", "sparkline"],
                "Line / area / bar / sparkline time-series marks.",
            ),
            (
                "tech-viz-heatmap",
                ["heatmap", "heatmap-status-grid"],
                "A heatmap / status-grid mark.",
            ),
            (
                "tech-viz-data-table",
                [
                    "table-view",
                    "virtualized-table",
                    "tables",
                    "table",
                    "reference-tables",
                    "list",
                ],
                "A tabular/data-table surface. NOTE: only the 3 records carrying "
                "``virtualized-table`` state virtualization; the wider table support "
                "is for tables, not for a virtualized implementation.",
            ),
            (
                "tech-viz-log-stream",
                [
                    "logs",
                    "streaming",
                    "real-time-streaming",
                    "request-log",
                    "process-monitor",
                    "resource-monitor",
                    "session-recording",
                    "log-stream",
                ],
                "A live log / event stream surface.",
            ),
            (
                "tech-viz-waterfall-timeline",
                ["trace-waterfall", "waterfall-timeline"],
                "A waterfall/timeline mark (the agent-ops trace waterfall).",
            ),
            (
                "tech-viz-rendering-performance",
                [
                    "sampling-decimation",
                    "rendering-performance",
                    "small-fast",
                    "lazy-rendering",
                    "resize-observer",
                    "gpu-rendering",
                    "graphics-protocol",
                    "terminal-rendering",
                    "canvas",
                    "canvas-vs-svg",
                    "svg-canvas",
                ],
                "Renderer/performance technique. NOTE: only 2 records state "
                "``sampling-decimation`` specifically.",
            ),
        ],
    ),
    (
        "grp-interaction",
        "Interaction",
        [
            (
                "tech-int-keyboard-first",
                ["keyboard-first", "keyboard-shortcuts", "vi-mode"],
                "Keyboard-first operation / shortcut surface.",
            ),
            (
                "tech-int-focus-management",
                ["focus-management"],
                "Focus management for keyboards/screen readers.",
            ),
            (
                "tech-int-aria-live",
                [
                    "aria",
                    "accessibility-aria",
                    "live-regions",
                    "screen-reader",
                    "table-semantics",
                ],
                "ARIA / live-region / semantic-markup accessibility technique.",
            ),
            (
                "tech-int-live-follow",
                ["live-follow", "live-refresh", "live-updates", "real-time", "real-time-metrics"],
                "Live-follow / real-time update behavior.",
            ),
            (
                "tech-int-sort-filter",
                ["sort-filter", "sort", "fuzzy-filter", "query-builder"],
                "Sort / filter / query surfaces.",
            ),
            (
                "tech-int-empty-error-states",
                ["empty-state", "empty-error-states"],
                "Empty and error states.",
            ),
            (
                "tech-int-skeleton-loading",
                ["skeleton-loading", "spinner", "progress"],
                "Loading indicators (skeleton/spinner/progress).",
            ),
            (
                "tech-int-reduced-motion",
                ["reduced-motion"],
                "prefers-reduced-motion escape hatch.",
            ),
        ],
    ),
    (
        "grp-visual",
        "Visual system",
        [
            (
                "tech-vis-design-tokens",
                [
                    "design-tokens",
                    "color-tokens",
                    "theme-config",
                    "themes",
                    "theming",
                    "dark-theme",
                    "light-theme",
                    "light-mode",
                    "dark-first-theming",
                    "monochrome-palette",
                    "color-palette",
                    "color-profiles",
                ],
                "Token / theme layer and its palette values.",
            ),
            (
                "tech-vis-colorblind-safe-status",
                [
                    "colorblind-safe-status",
                    "colorblind-safe",
                    "sequential-color",
                    "diverging-color",
                    "categorical-color",
                    "color-perception",
                    "color",
                    "color-scales",
                ],
                "Color-safe / perceptual color technique.",
            ),
            (
                "tech-vis-motion-easing",
                ["motion-easing"],
                "Motion easing system.",
            ),
            (
                "tech-vis-accent-economy",
                ["accent-economy"],
                "Restrained accent usage.",
            ),
            (
                "tech-vis-type-scale",
                ["type-scale", "typography-scale", "ligatures"],
                "Type scale / typography.",
            ),
            (
                "tech-vis-forced-colors",
                ["forced-colors"],
                "forced-colors / high-contrast mode support.",
            ),
            (
                "tech-vis-icon-family",
                ["icon-family"],
                "A single icon family.",
            ),
            (
                "tech-vis-elevation-model",
                ["elevation-model"],
                "A structural elevation model.",
            ),
        ],
    ),
    (
        "grp-trust-ops",
        "Trust / attention",
        [
            (
                "tech-trust-causal-lineage",
                ["span-tree", "traces-spans", "tracing"],
                "Causal lineage over spans/traces.",
            ),
            (
                "tech-trust-alerting",
                ["alerting", "alerting-rules", "monitors", "fraud-alerts"],
                "An alerting surface and its rules.",
            ),
            (
                "tech-trust-status-indicator",
                ["status"],
                "A status indicator/encoding.",
            ),
        ],
    ),
    (
        "grp-svg-diagram",
        "SVG / diagram craft",
        [
            (
                "tech-svg-theme-aware-svg",
                ["theme-aware-svg"],
                "SVG that follows theme tokens/currentColor.",
            ),
            (
                "tech-svg-accessible-svg",
                ["accessible-svg"],
                "SVG with accessible naming/semantics.",
            ),
            (
                "tech-svg-micro-visual",
                ["micro-visual", "sparkline", "color-bars", "braille-graphs"],
                "Small SVG/CSS micro-visuals.",
            ),
            (
                "tech-svg-path-tracer",
                ["path-tracer"],
                "A path tracer for flow/route lines.",
            ),
            (
                "tech-svg-print-safe-svg",
                ["print-safe-svg"],
                "Print-safe SVG (labels as text, no hard fills).",
            ),
        ],
    ),
    (
        "grp-money",
        "Money",
        [
            (
                "tech-money-cost-attribution",
                ["cost-tracking"],
                "Attributing cost to runs/agents.",
            ),
            (
                "tech-money-billing",
                ["payments", "usage-based-pricing"],
                "Billing / usage-based pricing surfaces.",
            ),
        ],
    ),
    (
        "grp-agent-ops",
        "Agent operations",
        [
            (
                "tech-ops-trace-tree",
                ["span-tree", "trace-waterfall", "traces-spans", "tracing", "waterfall-timeline"],
                "The trace/span tree and its waterfall.",
            ),
            (
                "tech-ops-eval-loop",
                [
                    "online-evaluation",
                    "eval",
                    "llm-evaluation",
                    "eval-narratives",
                    "scorer-config",
                    "pytest-style-scorers",
                    "experiment-comparison",
                    "regression-suite",
                    "prompt-comparison",
                    "dataset-management",
                    "datasets",
                    "rl-environments",
                    "playground-iteration",
                    "benchmarking",
                    "eval-monitoring",
                    "eval-metrics",
                ],
                "The dataset -> run -> score -> compare evaluation loop.",
            ),
            (
                "tech-ops-prompt-registry",
                ["prompt-versioning", "prompt-deployment", "prompt-hub"],
                "A prompt registry/versioning surface.",
            ),
            (
                "tech-ops-observability",
                [
                    "agent-observability",
                    "observability",
                    "otel-instrumentation",
                    "vendor-agnostic-tracing",
                    "sdk-instrumentation",
                    "gateway-proxy",
                    "mcp",
                ],
                "Agent/model observability and instrumentation.",
            ),
            (
                "tech-ops-metrics",
                [
                    "metrics",
                    "real-time-metrics",
                    "latency-metrics",
                    "metrics-dashboard",
                    "gpu-metrics",
                    "latency-percentiles",
                    "funnels",
                ],
                "Metrics/latency measurement surfaces. NOTE: this is where the generic "
                "``metrics`` / ``latency-metrics`` labels live; they never backed a "
                "'provenance' claim.",
            ),
            (
                "tech-ops-session-grouping",
                ["session-grouping"],
                "Grouping many sessions/runs into one view.",
            ),
            (
                "tech-ops-issue-tracking",
                ["error-tracking", "incident-view", "error-code-reference", "issues-list"],
                "Error/issue/incident tracking surfaces.",
            ),
            (
                "tech-ops-release-feed",
                ["changelog", "deployments", "provisioning", "serverless-containers", "webhooks"],
                "Release/deploy feeds. NOTE: this is a release feed, not an actor audit "
                "trail; the deleted ``trust-audit-trail`` was promoted from these labels.",
            ),
        ],
    ),
]

# Nodes with direct but below-bar support: kept for transparency, never promoted.
THIN_NODES: list[tuple[str, list[str], str, str]] = [
    ("thin-ia-modal-sheet", ["modal-sheet"], "grp-ia-layout", "Modal/sheet disclosure."),
    ("thin-ia-overflow-drawer", ["overflow-drawer"], "grp-ia-layout", "Overflow drawer."),
    ("thin-viz-gauge", ["gauge"], "grp-data-viz", "A gauge mark."),
    ("thin-viz-small-multiples", ["small-multiples"], "grp-data-viz", "Small multiples."),
    (
        "thin-viz-threshold-bands",
        ["threshold-bands", "staleness-threshold"],
        "grp-data-viz",
        "Threshold/staleness bands.",
    ),
    ("thin-int-confirmation-door", ["confirmation-door"], "grp-interaction", "A confirmation step."),
    ("thin-svg-flow-diagram", ["flow-diagram"], "grp-svg-diagram", "Flow-diagram topology."),
    ("thin-ops-self-host", ["self-host"], "grp-agent-ops", "Self-hosting."),
]

# Nodes deleted by the repair: no source record states the technique. Each records
# the broad label(s) that previously manufactured its support.
DELETED_NODES: list[dict[str, object]] = [
    {
        "id": "tech-ia-board-per-domain",
        "prior_support": 55,
        "promoted_from": ["dashboards", "dashboard", "dashboard-grid"],
        "reason": "No record carries board-per-domain; generic dashboards do not state "
        "division into work/money/health/decisions. Recast as tech-ia-dashboard-layout "
        "(generic board), and keep the domain split as [P] local policy in r4/r5.",
    },
    {
        "id": "tech-trust-source-provenance",
        "prior_support": 40,
        "promoted_from": ["logs", "metrics", "cost-tracking", "data-join"],
        "reason": "No record states source-provenance. logs/metrics/cost-tracking "
        "directly state log, metric and cost surfaces (now their own nodes); they do "
        "not entail a provenance/attribution claim. Provenance survives only as [P].",
    },
    {
        "id": "tech-trust-degraded-banner",
        "prior_support": 11,
        "promoted_from": ["status"],
        "reason": "No record states a named-dependency degraded banner; generic status "
        "is now tech-trust-status-indicator. The banner is a [P] local policy.",
    },
    {
        "id": "tech-trust-uncertainty-encoding",
        "prior_support": 3,
        "promoted_from": ["online-evaluation", "eval", "chart-types"],
        "reason": "No record states uncertainty/partiality/unmeasured encoding. Eval and "
        "chart labels are now their own nodes. Uncertainty display is [P].",
    },
    {
        "id": "tech-money-budget-thresholds",
        "prior_support": 19,
        "promoted_from": ["alerting", "alerting-rules"],
        "reason": "No record states a budget threshold; generic alerting is "
        "tech-trust-alerting. Budget thresholds are a [P] local policy.",
    },
    {
        "id": "tech-money-quota-wallet",
        "prior_support": 7,
        "promoted_from": ["payments", "pricing"],
        "reason": "No record states quota or wallet; payments/usage pricing is now "
        "tech-money-billing. Quota/wallet/lease composition is [P] local policy.",
    },
    {
        "id": "tech-trust-audit-trail",
        "prior_support": 14,
        "promoted_from": ["changelog", "deployments", "provisioning", "webhooks"],
        "reason": "No record states an actor audit trail; those labels directly state a "
        "release/deploy feed (now tech-ops-release-feed). Audit trail is [P].",
    },
]

# Canonical category crosswalk: value -> raw category values folded into it.
CATEGORY_CROSSWALK: dict[str, list[str]] = {
    "cat-ops-dashboard": ["ops-dashboard", "product-ops"],
    "cat-agent-ops-room": [
        "agent-ops-room",
        "eval-platform",
        "eval-framework",
        "opentelemetry-instrumentation",
    ],
    "cat-design-craft": ["design-craft", "dataviz-craft"],
    "cat-terminal-app": [
        "terminal-app",
        "terminal-emulator",
        "terminal-recording",
        "tui-framework",
        "tui-monitor",
        "tui-tool",
        "cli-tool",
    ],
    "cat-chart-library": ["chart-library", "chart-gallery"],
    "cat-reference-standard": ["reference-standard"],
    "cat-component-kit": ["component-kit"],
    "cat-case-study": ["case-study"],
    "cat-design-system": ["design-system"],
}

# Canonical stack crosswalk. ``docs-site`` is folded into ``none`` because the
# agent-ops sources are documentation pages and do not reveal a product stack.
STACK_CROSSWALK: dict[str, list[str]] = {
    "stk-none": ["none", "docs-site"],
    "stk-unknown": ["unknown"],
    "stk-chart-lib": ["vega-lite", "echarts", "recharts", "vega", "observable-plot"],
    "stk-svg-css-only": ["svg-css-only"],
    "stk-vanilla-js": ["vanilla-js"],
    "stk-react": ["react"],
    "stk-d3": ["d3"],
    "stk-tailwind": ["tailwind"],
    "stk-typescript": ["typescript"],
    "stk-tui-go": ["go"],
    "stk-tui-rust": ["rust"],
    "stk-tui-python": ["python"],
    "stk-tui-native": ["zig", "c", "c++"],
    "stk-canvas-webgl": ["canvas"],
}

QUALITY_SIGNALS = [
    "authority",
    "recency",
    "accessibility_evidence",
    "performance_evidence",
    "demonstrates",
    "open_implementation",
    "single_source_risk",
]


# --------------------------------------------------------------------------- #
# Corpus loading
# --------------------------------------------------------------------------- #
class Record:
    """One facet-corpus record, reduced to what the taxonomy needs."""

    __slots__ = ("family", "uri", "sha", "sha_full", "title", "techniques", "category",
                 "aesthetic", "stack", "quality")

    def __init__(self, family: str, raw: dict) -> None:
        self.family = family
        self.uri = raw["uri"]
        self.sha_full = raw["sha256"]
        self.sha = raw["sha256"][:16]
        self.title = raw.get("title", "")
        self.techniques = set(raw.get("techniques", []))
        self.category = raw.get("category", "")
        self.aesthetic = raw.get("aesthetic", "")
        self.stack = set(raw.get("stack", []))
        self.quality = raw.get("quality", {})

    def example(self) -> dict:
        return {"family": self.family, "uri": self.uri, "sha256": self.sha, "title": self.title}


def load_corpus() -> tuple[list[Record], list[dict]]:
    """Load the five family corpora and return (records, input hashes)."""
    records: list[Record] = []
    inputs: list[dict] = []
    for family in FAMILIES:
        path = CORPUS_DIR / f"{family}.jsonl"
        payload = path.read_bytes()
        count = 0
        for line in payload.decode("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            records.append(Record(family, json.loads(line)))
            count += 1
        inputs.append(
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "records": count,
            }
        )
    return records, inputs


# --------------------------------------------------------------------------- #
# Node construction helpers
# --------------------------------------------------------------------------- #
def _family_counts(records: Iterable[Record]) -> dict[str, int]:
    counts = collections.Counter(r.family for r in records)
    return {f: counts[f] for f in FAMILIES if counts.get(f)}


def _examples(records: list[Record]) -> tuple[list[dict], list[str]]:
    """Round-robin across families so examples are not one-family dominated."""
    by_family: dict[str, list[Record]] = {f: [] for f in FAMILIES}
    for r in records:
        by_family[r.family].append(r)
    for lst in by_family.values():
        lst.sort(key=lambda r: r.uri)
    ordered: list[Record] = []
    idx = 0
    while len(ordered) < min(MAX_EXAMPLES, len(records)):
        added = False
        for f in FAMILIES:
            if idx < len(by_family[f]) and len(ordered) < MAX_EXAMPLES:
                ordered.append(by_family[f][idx])
                added = True
        if not added:
            break
        idx += 1
    return [r.example() for r in ordered], [r.sha for r in ordered]


def make_node(node_id: str, parent: str, kind: str, facet: dict, matched: list[Record],
              note: str) -> dict:
    by_family = _family_counts(matched)
    examples, shas = _examples(matched)
    meets = len(matched) >= MIN_SUPPORT
    return {
        "id": node_id,
        "parent": parent,
        "kind": kind,
        "facet": facet,
        "support": len(matched),
        "support_by_family": by_family,
        "independent_families": len(by_family),
        "meets_three_source_rule": meets,
        "examples": examples,
        "example_shas": shas,
        "note": note,
    }


def make_technique_node(node_id: str, parent: str, labels: list[str],
                        matched: list[Record], note: str, thin: bool = False) -> dict:
    node = make_node(
        node_id,
        parent,
        "thin" if thin else "cluster",
        {"technique": node_id},
        matched,
        note if thin else f"{note} Direct labels: {', '.join(sorted(labels))}.",
    )
    if thin:
        node["note"] = f"Below the >={MIN_SUPPORT}-source bar; not promoted. {note}"
    return node


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
def build() -> dict:
    records, inputs = load_corpus()

    nodes: list[dict] = []
    crosswalk: dict[str, list[str]] = {}

    # -- root + dimensions --------------------------------------------------- #
    root = make_node(
        "root", None, "root", {"schema": "control-room-taxonomy/v1", "families": FAMILIES},
        records, "The whole 5-family corpus. Nodes overlap; supports do not sum.",
    )
    root["facet"] = {"schema": "control-room-taxonomy/v1", "families": FAMILIES}
    nodes.append(root)
    for dim, label in [
        ("dim-category", "category"),
        ("dim-aesthetic", "aesthetic"),
        ("dim-stack", "stack"),
        ("dim-technique", "technique"),
        ("dim-evidence", "evidence"),
    ]:
        nodes.append(
            {
                "id": dim,
                "parent": "root",
                "kind": "dimension",
                "facet": {"dimension": label},
                "support": len(records),
                "support_by_family": {},
                "independent_families": len(FAMILIES),
                "meets_three_source_rule": True,
                "examples": [],
                "example_shas": [],
                "note": f"What the artifact's {label} is.",
            }
        )

    # -- category cluster branch -------------------------------------------- #
    for node_id, values in CATEGORY_CROSSWALK.items():
        matched = [r for r in records if r.category in values]
        nodes.append(
            make_node(node_id, "dim-category", "cluster", {"category": node_id},
                      matched, f"Raw category values folded in: {', '.join(sorted(values))}.")
        )

    # -- aesthetic cluster branch ------------------------------------------- #
    aesthetic_values = sorted({r.aesthetic for r in records if r.aesthetic})
    for value in aesthetic_values:
        matched = [r for r in records if r.aesthetic == value]
        nodes.append(
            make_node(f"aes-{value}", "dim-aesthetic", "cluster", {"aesthetic": value},
                      matched, "Raw aesthetic value.")
        )

    # -- stack cluster branch ----------------------------------------------- #
    for node_id, values in STACK_CROSSWALK.items():
        matched = [r for r in records if r.stack & set(values)]
        nodes.append(
            make_node(node_id, "dim-stack", "cluster", {"stack": node_id},
                      matched, f"Raw stack values folded in: {', '.join(sorted(values))}.")
        )

    # -- quality signal branch ---------------------------------------------- #
    for signal in QUALITY_SIGNALS:
        matched = [r for r in records if signal in r.quality]
        nodes.append(
            make_node(f"ev-{signal}", "dim-evidence", "signal", {"signal": signal},
                      matched, "Records carrying this quality signal.")
        )

    # -- technique branch ---------------------------------------------------- #
    # Track per-node matched sets so groups can union their children exactly.
    matched_by_node: dict[str, list[Record]] = {}
    for group_id, group_label, children in TECH_GROUPS:
        for node_id, labels, _note in children:
            matched = [r for r in records if r.techniques & set(labels)]
            matched_by_node[node_id] = matched
            crosswalk[node_id] = list(labels)
        # Group support is the union of its children's matched records.
        group_records = {r.sha: r for node_id, _, _ in children for r in matched_by_node[node_id]}
        matched_by_node[group_id] = list(group_records.values())
        crosswalk[group_id] = sorted({lab for _, labs, _ in children for lab in labs})
        nodes.append(
            make_node(group_id, "dim-technique", "group", {"group": group_label},
                      matched_by_node[group_id],
                      f"Union of its promoted child clusters. {group_label}.")
        )
        # Child nodes are appended after their group so parent-before-child holds.
        for node_id, labels, note in children:
            nodes.append(
                make_technique_node(node_id, group_id, labels, matched_by_node[node_id], note)
            )

    # -- thin nodes ---------------------------------------------------------- #
    for node_id, labels, parent, note in THIN_NODES:
        matched = [r for r in records if r.techniques & set(labels)]
        matched_by_node[node_id] = matched
        crosswalk[node_id] = list(labels)
        nodes.append(
            make_technique_node(node_id, parent, labels, matched, note, thin=True)
        )

    # -- repair accounting --------------------------------------------------- #
    mapped_labels = {lab for labs in crosswalk.values() for lab in labs}
    label_counts = collections.Counter(
        lab for r in records for lab in r.techniques
    )
    unmapped = {
        lab: count for lab, count in sorted(label_counts.items(), key=lambda x: (-x[1], x[0]))
        if lab not in mapped_labels
    }

    thin_kept = [n for n in nodes if n["kind"] == "thin"]

    total_technique_records = len({r.sha for r in records if r.techniques & mapped_labels})
    nodes_by_id = {n["id"]: n for n in nodes}
    if "dim-technique" in nodes_by_id:
        nodes_by_id["dim-technique"]["support"] = total_technique_records
        nodes_by_id["dim-technique"]["support_by_family"] = _family_counts(
            [r for r in records if r.techniques & mapped_labels]
        )

    by_family = collections.Counter(r.family for r in records)
    taxonomy = {
        "schema": "control-room-taxonomy/v1",
        "phase": "p0_repair_taxonomy",
        "corpus": "control_room_research",
        "min_support": MIN_SUPPORT,
        "inputs": inputs,
        "corpus_totals": {
            "records_total": len(records),
            "by_family": {f: by_family[f] for f in FAMILIES},
            "unique_technique_labels": len(label_counts),
            "canonical_leaves": len(crosswalk),
            "promoted_leaves": len([n for n in nodes if n["kind"] == "cluster" and n["id"].startswith("tech-") and n["meets_three_source_rule"]]),
            "thin_leaves": len(thin_kept),
            "records_with_mapped_technique": total_technique_records,
            "mapped_labels": len(mapped_labels),
            "unmapped_labels": [[lab, count] for lab, count in unmapped.items()],
            "unmapped_mentions": sum(unmapped.values()),
        },
        "method": (
            "Direct raw-label support only. support = distinct corpus records whose own "
            "technique labels name the node's technique. A broad label backs its umbrella "
            "node and nothing narrower; labels with no direct home stay unmapped; nodes "
            "supported only by promotion are deleted (see repair.deleted_nodes)."
        ),
        "crosswalk": crosswalk,
        "repair": {
            "deleted_nodes": DELETED_NODES,
            "renamed_nodes": [
                {"from": "tech-viz-virtualized-table", "to": "tech-viz-data-table",
                 "reason": "The label set is tables; only 3 records state virtualization."},
                {"from": "tech-viz-heatmap-status-grid", "to": "tech-viz-heatmap",
                 "reason": "Direct marks are heatmap/heatmap-status-grid (4 records)."},
                {"from": "tech-viz-timeline-gantt", "to": "tech-viz-waterfall-timeline",
                 "reason": "The direct mark is a trace/waterfall timeline, not a gantt."},
                {"from": "tech-viz-sampling-decimation", "to": "tech-viz-rendering-performance",
                 "reason": "Renderer/performance labels; only 2 records state decimation."},
            ],
            "recast_nodes": [
                {"from": "tech-ia-board-per-domain", "to": "tech-ia-dashboard-layout",
                 "reason": "Keep the generic board support; drop the unsupported domain split."},
            ],
        },
        "split_merge": {
            "rule": "Never split a broad label into a narrower leaf it does not state.",
            "merges": [
                {
                    "from": ["dashboards", "dashboard", "dashboard-grid"],
                    "into": "tech-ia-dashboard-layout",
                    "reason": "Board labels denote one generic board/grid surface.",
                },
                {
                    "from": ["widget-catalog", "widgets", "panel-library", "tui-components",
                             "blocks", "dashboard-blocks", "dashboard-components", "panels"],
                    "into": "tech-ia-widget-catalog",
                    "reason": "Widget/panel catalog synonyms across F2/F3/F4.",
                },
                {
                    "from": ["line-chart", "area-chart", "bar-chart", "time-series", "sparkline"],
                    "into": "tech-viz-time-series-marks",
                    "reason": "Time-series mark synonyms.",
                },
                {
                    "from": ["logs", "streaming", "real-time-streaming", "request-log",
                             "process-monitor", "resource-monitor", "session-recording"],
                    "into": "tech-viz-log-stream",
                    "reason": "Live log/event surface synonyms.",
                },
                {
                    "from": ["table-view", "tables", "table", "reference-tables", "list",
                             "virtualized-table"],
                    "into": "tech-viz-data-table",
                    "reason": "Table synonyms; virtualization kept as a sub-claim note only.",
                },
                {
                    "from": ["design-tokens", "color-tokens", "theme-config", "themes",
                             "theming", "dark-theme", "light-theme", "light-mode",
                             "dark-first-theming", "monochrome-palette", "color-palette"],
                    "into": "tech-vis-design-tokens",
                    "reason": "Token/theme synonyms.",
                },
            ],
            "deleted_splits": [
                {"umbrella": "chart-types/charts", "into": ["viz-time-series-marks",
                 "viz-heatmap-status-grid", "viz-gauge"],
                 "reason": "Deleted: chart-types states chart types, not those marks. "
                 "chart-types is now its own umbrella tech-viz-chart-types."},
                {"umbrella": "status", "into": ["viz-heatmap-status-grid",
                 "trust-degraded-banner"],
                 "reason": "Deleted: status is now tech-trust-status-indicator; the "
                 "degraded banner was promotion."},
                {"umbrella": "metrics", "into": ["trust-source-provenance",
                 "viz-time-series-marks"],
                 "reason": "Deleted: metrics is now tech-ops-metrics; provenance was promotion."},
                {"umbrella": "logs", "into": ["viz-log-stream", "trust-source-provenance"],
                 "reason": "Deleted: logs back the log stream only; provenance was promotion."},
                {"umbrella": "cost-tracking", "into": ["money-cost-attribution",
                 "trust-source-provenance"],
                 "reason": "Deleted: cost-tracking backs cost attribution only."},
                {"umbrella": "alerting/alerting-rules", "into": ["trust-alerting",
                 "money-budget-thresholds"],
                 "reason": "Deleted: alerting backs alerting only; budget thresholds were promotion."},
                {"umbrella": "accessibility", "into": ["svg-accessible-svg",
                 "int-focus-management", "vis-colorblind-safe-status", "int-reduced-motion"],
                 "reason": "Deleted: accessibility is not a split label; each technique is "
                 "backed only by its own labels."},
            ],
        },
        "nodes": nodes,
    }
    return taxonomy


def main() -> None:
    taxonomy = build()
    TAXONOMY_PATH.write_text(json.dumps(taxonomy, indent=2) + "\n", encoding="utf-8")
    totals = taxonomy["corpus_totals"]
    print(f"wrote {TAXONOMY_PATH.relative_to(ROOT)}")
    print(f"  nodes: {len(taxonomy['nodes'])}  promoted: {totals['promoted_leaves']}"
          f"  thin: {totals['thin_leaves']}")
    print(f"  mapped labels: {totals['mapped_labels']}/{totals['unique_technique_labels']}"
          f"  unmapped mentions: {totals['unmapped_mentions']}")
    for deleted in taxonomy["repair"]["deleted_nodes"]:
        print(f"  DELETED {deleted['id']} (was {deleted['prior_support']})")


if __name__ == "__main__":
    main()
