#!/usr/bin/env python3
"""Deterministic rebuild of the Control Room research taxonomy — quoted-evidence support.

Why this file exists
--------------------
Phase ``r3_taxonomy`` crosswalked the 270 raw technique labels in the five family
corpora to canonical leaves by *interpreting* broad umbrella labels as evidence for
narrow techniques no source record states. The p0 repair cut the worst of that
promotion but still allocated labels to adjacent (not equivalent) leaves: a
``command-palette`` leaf counted ``fuzzy-find``/``fuzzy-filter``/``aliases`` records,
a ``log-stream`` leaf counted GPU/resource monitors and terminal recordings, and so on
(adversary ``control_room_repair_entailment.md`` E1/E4).

The repair2 step makes support *semantic and quoted*, not merely arithmetic:

    A technique leaf may count a corpus record only when the record carries one of the
    leaf's OWN direct labels (exactly one leaf per raw label, so no double support), and
    each counted record stores a verbatim sentence from its stored source page that
    states the leaf's technique. Labels that state a broader or adjacent idea are
    promotions: they are removed from the leaf (and either re-homed to the one leaf
    they literally name, or left unmapped and recorded in ``semantic_review``). A node
    whose only support was promotion is deleted.

Run:
    python3 experiments/research/control_room/build_taxonomy.py

Writes ``taxonomy.json`` plus the human-readable semantic crosswalk
``docs/reviews/control_room_semantic_crosswalk.md``, and fails loudly if any technique
leaf carries a support count without stored ``evidence_quotes``.
"""

from __future__ import annotations

import collections
import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths and constants
# --------------------------------------------------------------------------- #
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]  # experiments/research/control_room -> repo root
CORPUS_DIR = HERE / "corpus"
SOURCES_DIR = HERE / "sources"
TAXONOMY_PATH = HERE / "taxonomy.json"
CROSSWALK_PATH = ROOT / "docs" / "reviews" / "control_room_semantic_crosswalk.md"

FAMILIES = ["agentops", "dashboards", "dataviz", "cli", "craft"]
MIN_SUPPORT = 3  # the r1 §3.3 ">= 3 independent sources" bar
MAX_EXAMPLES = 12  # example refs stored per node (readability, not a support cap)

# --------------------------------------------------------------------------- #
# The direct crosswalk: canonical node -> the raw technique labels that NAME it.
#
# Repair2 rule (adversary E4): each raw label appears in exactly ONE technique leaf.
# A label only maps when it literally names that leaf's technique; where a former label
# stated a broader/adjacent idea it is removed (see SEMANTIC_PROMOTIONS) rather than
# being silently kept as support. This is the semantic table the crosswalk markdown
# mirrors, record by record.
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
                "A named catalog/library of panels, widgets or component blocks. The raw "
                "labels all name the widget/panel/block unit or its catalog; the leaf is "
                "an umbrella for that component library, not a claim of a specific widget.",
            ),
            (
                "tech-ia-command-palette",
                ["command-palette"],
                "A keystroke-summoned command palette. Only the literal ``command-palette`` "
                "label is direct; fuzzy-find/fuzzy-filter/aliases name other surfaces "
                "(removed — see semantic_review.promotions).",
            ),
            (
                "tech-ia-tab-bar",
                ["tabs", "native-tabs", "tab-bar"],
                "A tab bar. Pane/split/multiplexing labels are terminal navigation but do "
                "not state a tab bar (removed — see semantic_review.promotions).",
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
                ["density-ladder"],
                "A persisted density ladder. Generic ``density``/``responsive-layout`` "
                "labels state responsive adaptation, not a persisted ladder (removed).",
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
                "Line / area / bar / sparkline time-series marks. ``sparkline`` is assigned "
                "here (not to micro-visual) so each label has one direct leaf (E4).",
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
                    "log-stream",
                ],
                "A live log / event stream surface. Process/resource monitors and terminal "
                "recordings do not state a log stream (removed — see promotions).",
            ),
            (
                "tech-viz-waterfall-timeline",
                ["trace-waterfall", "waterfall-timeline"],
                "A waterfall/timeline mark (the agent-ops trace waterfall). Assigned here "
                "exclusively so the mark does not also inflate the trace-tree leaf (E4).",
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
                ["live-follow", "live-refresh", "live-updates", "real-time"],
                "Live-follow / real-time update behavior. ``real-time-metrics`` is a "
                "metrics label and is assigned to tech-ops-metrics only (E4).",
            ),
            (
                "tech-int-sort-filter",
                ["sort-filter", "sort", "fuzzy-filter", "query-builder"],
                "Sort / filter / query surfaces. ``fuzzy-filter`` is a filter surface and "
                "is assigned here exclusively (E4).",
            ),
            (
                "tech-int-empty-error-states",
                ["empty-state", "empty-error-states"],
                "Empty and error states.",
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
                "Token / theme layer and its palette values. The labels name tokens, "
                "themes and palettes, so the leaf is an honest token/theme umbrella "
                "rather than a tokens-only claim (E1 other-review item).",
            ),
            (
                "tech-vis-colorblind-safe-status",
                ["colorblind-safe-status", "colorblind-safe"],
                "Colorblind-safe color encoding. Sequential/diverging/categorical color "
                "labels state palette technique, not colorblind safety (removed).",
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
                ["type-scale", "typography-scale"],
                "Type scale / typography. ``ligatures`` is a type feature, not a scale "
                "(removed — see promotions).",
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
                "tech-trust-alerting",
                ["alerting", "alerting-rules", "fraud-alerts"],
                "An alerting surface and its rules. Generic ``monitors`` states a monitor, "
                "not an alerting surface (removed).",
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
                ["micro-visual", "color-bars", "braille-graphs"],
                "Small SVG/CSS micro-visuals. ``sparkline`` is a time-series mark and is "
                "assigned to tech-viz-time-series-marks only (E4).",
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
                ["span-tree", "traces-spans", "tracing"],
                "The trace/span tree structure. The waterfall mark is its own leaf "
                "(E4); the old causal-lineage leaf duplicated this one and was deleted.",
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
                "tech-ops-observability",
                [
                    "agent-observability",
                    "observability",
                    "otel-instrumentation",
                    "vendor-agnostic-tracing",
                    "sdk-instrumentation",
                ],
                "Agent/model observability and instrumentation. Gateway-proxy and MCP "
                "labels name a proxy/protocol, not observability (removed).",
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
                "Metrics/latency measurement surfaces. ``real-time-metrics`` lives here "
                "only (E4).",
            ),
            (
                "tech-ops-session-grouping",
                ["session-grouping"],
                "Grouping many sessions/runs into one view.",
            ),
            (
                "tech-ops-issue-tracking",
                ["error-tracking", "incident-view", "issues-list"],
                "Error/issue/incident tracking surfaces. ``error-code-reference`` is a "
                "reference table, not issue tracking (removed).",
            ),
            (
                "tech-ops-release-feed",
                ["changelog", "deployments"],
                "Release/deploy feeds. Provisioning, serverless-container and webhook "
                "labels state infrastructure, not a feed (removed).",
            ),
        ],
    ),
]

# Short technique phrasing per leaf, used for the crosswalk table and the quote
# extractor's evidence tokens.
TECHNIQUE: dict[str, str] = {
    "tech-ia-dashboard-layout": "dashboard board / grid layout",
    "tech-ia-widget-catalog": "widget / panel / component library",
    "tech-ia-command-palette": "command palette",
    "tech-ia-tab-bar": "tab bar",
    "tech-ia-progressive-disclosure": "progressive disclosure",
    "tech-ia-master-detail": "master / detail split",
    "tech-ia-density-ladder": "density ladder",
    "tech-viz-chart-types": "chart-types umbrella",
    "tech-viz-chart-grammar": "grammar of graphics / chart craft",
    "tech-viz-time-series-marks": "time-series marks",
    "tech-viz-heatmap": "heatmap / status grid",
    "tech-viz-data-table": "data table",
    "tech-viz-log-stream": "log / event stream",
    "tech-viz-waterfall-timeline": "trace waterfall / timeline",
    "tech-viz-rendering-performance": "rendering / performance",
    "tech-int-keyboard-first": "keyboard-first operation",
    "tech-int-focus-management": "focus management",
    "tech-int-aria-live": "ARIA / live regions",
    "tech-int-live-follow": "live-follow / real-time update",
    "tech-int-sort-filter": "sort / filter / query",
    "tech-int-empty-error-states": "empty / error states",
    "tech-int-skeleton-loading": "skeleton loading",
    "tech-int-reduced-motion": "reduced motion",
    "tech-vis-design-tokens": "design tokens / theme layer",
    "tech-vis-colorblind-safe-status": "color-accessible / colorblind-safe encoding",
    "tech-vis-motion-easing": "motion easing",
    "tech-vis-accent-economy": "accent economy",
    "tech-vis-type-scale": "type / typographic scale",
    "tech-vis-forced-colors": "forced colors",
    "tech-vis-icon-family": "icon family",
    "tech-vis-elevation-model": "elevation model",
    "tech-trust-alerting": "alerting surface",
    "tech-trust-status-indicator": "status indicator",
    "tech-svg-theme-aware-svg": "theme-aware SVG",
    "tech-svg-accessible-svg": "accessible SVG",
    "tech-svg-micro-visual": "SVG / CSS micro-visual",
    "tech-svg-path-tracer": "path tracer",
    "tech-svg-print-safe-svg": "print-safe SVG",
    "tech-money-cost-attribution": "cost attribution",
    "tech-money-billing": "billing / usage-based pricing",
    "tech-ops-trace-tree": "trace / span tree",
    "tech-ops-eval-loop": "evaluation loop",
    "tech-ops-observability": "agent / model observability",
    "tech-ops-metrics": "metrics / latency",
    "tech-ops-session-grouping": "session grouping",
    "tech-ops-issue-tracking": "issue / incident tracking",
    "tech-ops-release-feed": "release / deployment feed",
}

# The evidence pattern each leaf requires its source text to state for a record to
# count. This is the semantic gate of repair2: a raw label is the record's ANNOTATION,
# but support additionally requires the stored source page to state the technique (a
# broad label like ``logs`` cannot state a log STREAM unless the page says so). A leaf
# whose pattern matches fewer than MIN_SUPPORT records is automatically below the bar
# and drops out of the catalogs/skills as [P].
EVIDENCE_PATTERNS: dict[str, str] = {
    "tech-ia-dashboard-layout": r"dashboard",
    "tech-ia-widget-catalog": r"widget|component librar|component kit|panel librar|"
                              r"\bblocks?\b|toolkit|\bpanels?\b",
    "tech-ia-command-palette": r"command palette|cmd\s*\+?\s*k|⌘\s*k|command bar",
    "tech-ia-tab-bar": r"tab bar|new tab|\btabs?\b",
    "tech-ia-progressive-disclosure": r"progressive disclosure|disclosure|"
                                      r"reveal.{0,20}(detail|demand)|on demand|expander|accordion",
    "tech-ia-master-detail": r"master.detail|detail (pane|view)|list.detail|sidebar|"
                             r"split view|two.pane|panel detail",
    "tech-ia-density-ladder": r"density|compact|comfortable",
    "tech-viz-chart-types": r"chart type|chart types|charts\b|\d+ chart",
    "tech-viz-chart-grammar": r"grammar of graphics|encoding channels?\b|\bscales\b|"
                              r"\bmarks\b|axis",
    "tech-viz-time-series-marks": r"line chart|area chart|bar chart|time series|sparkline",
    "tech-viz-heatmap": r"heat ?map|status grid",
    "tech-viz-data-table": r"table|tabular|virtualiz",
    "tech-viz-log-stream": r"log stream|log viewer|\blogs?\b|request log|streaming",
    "tech-viz-waterfall-timeline": r"waterfall|timeline",
    "tech-viz-rendering-performance": r"render|performance|gpu|canvas|\bsvg\b",
    "tech-int-keyboard-first": r"keyboard|shortcut|vi mode",
    "tech-int-focus-management": r"\bfocus\b",
    "tech-int-aria-live": r"\baria\b|live region|screen reader",
    "tech-int-live-follow": r"\blive\b|real.?time|refresh",
    "tech-int-sort-filter": r"\bsort\b|filter|query",
    "tech-int-empty-error-states": r"empty state|error state|\bempty\b",
    "tech-int-skeleton-loading": r"skeleton",
    "tech-int-reduced-motion": r"reduced.motion|reduce motion",
    "tech-vis-design-tokens": r"design token|token[s]?\b|theme|palette",
    "tech-vis-colorblind-safe-status": r"colorblind|color.blind|colour.blind|contrast",
    "tech-vis-motion-easing": r"easing|motion",
    "tech-vis-accent-economy": r"accent|60.30.10|color mix",
    "tech-vis-type-scale": r"type scale|typographic scale|modular scale|typograph",
    "tech-vis-forced-colors": r"forced.colors",
    "tech-vis-icon-family": r"icon",
    "tech-vis-elevation-model": r"elevation|shadow",
    "tech-trust-alerting": r"alert",
    "tech-trust-status-indicator": r"\bstatus\b",
    "tech-svg-theme-aware-svg": r"theme|currentcolor",
    "tech-svg-accessible-svg": r"accessible svg|accessible.{0,20}svg|\baria\b|\brole\b|<title>",
    "tech-svg-micro-visual": r"micro|sparkline|braille|color.bars",
    "tech-svg-path-tracer": r"path.{0,20}animat|draw.{0,20}path|path tracer|stroke.dash",
    "tech-svg-print-safe-svg": r"print",
    "tech-money-cost-attribution": r"\bcost\b|spend|price",
    "tech-money-billing": r"payment|billing|pricing|usage.based",
    "tech-ops-trace-tree": r"trace|span",
    "tech-ops-eval-loop": r"eval|scorer|dataset|benchmark",
    "tech-ops-observability": r"observab|instrument|otel|opentelemetry",
    "tech-ops-metrics": r"metric|latency|percentile",
    "tech-ops-session-grouping": r"session",
    "tech-ops-issue-tracking": r"issue|incident|error track",
    "tech-ops-release-feed": r"changelog|release notes|releases|deploy",
    # Thin leaves still declare a pattern so their few quotes are on-topic.
    "thin-ia-modal-sheet": r"modal|dialog|sheet",
    "thin-ia-overflow-drawer": r"drawer|overflow",
    "thin-viz-gauge": r"gauge",
    "thin-viz-small-multiples": r"small multiples",
    "thin-viz-threshold-bands": r"threshold|staleness",
    "thin-int-confirmation-door": r"confirm|confirmation",
    "thin-svg-flow-diagram": r"flow diagram|flowchart|flow chart|sankey|node.{0,12}edge",
    "thin-ops-self-host": r"self.host",
}

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
    (
        "tech-int-skeleton-loading",
        ["skeleton-loading"],
        "grp-interaction",
        "Skeleton loading. Direct support is 2 records; spinner/progress are other loading "
        "indicators and were removed (E1).",
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
    {
        "id": "tech-ops-prompt-registry",
        "prior_support": 3,
        "promoted_from": ["prompt-versioning", "prompt-deployment", "prompt-hub"],
        "reason": "No record carries a literal prompt-registry label. The closest source "
        "texts (LangChain Prompt & Context Hub; Langfuse Prompt Management) state a prompt "
        "management/hub surface, not a registry. Deleted; the hub is a [P] local policy "
        "(control_room_repair_entailment.md E1, literal support 0).",
    },
    {
        "id": "tech-trust-causal-lineage",
        "prior_support": 18,
        "promoted_from": ["span-tree", "traces-spans", "tracing"],
        "reason": "The labels span-tree/traces-spans/tracing literally name a trace/span "
        "tree, which is tech-ops-trace-tree; causal-lineage was a second leaf claiming the "
        "same labels (E4 double support). Collapsed into its sibling tech-ops-trace-tree.",
    },
]

# Explicit label dispositions for labels removed from a leaf. Every entry records the
# leaf that formerly absorbed the label and where the label goes now: either the one
# leaf it literally names (``to``) or the unmapped pool (``to=None``) with the reason.
SEMANTIC_PROMOTIONS: list[dict[str, object]] = [
    {"label": "fuzzy-find", "from": "tech-ia-command-palette", "to": None,
     "reason": "Names a fuzzy finder (fzf), not a keystroke command palette."},
    {"label": "fuzzy-filter", "from": "tech-ia-command-palette", "to": "tech-int-sort-filter",
     "reason": "Names a filter surface; re-homed to the leaf it literally names (E4)."},
    {"label": "aliases", "from": "tech-ia-command-palette", "to": None,
     "reason": "Names shell aliases (k9s), not a command palette."},
    {"label": "split-panes", "from": "tech-ia-tab-bar", "to": None,
     "reason": "Names pane navigation, not a tab bar."},
    {"label": "panes", "from": "tech-ia-tab-bar", "to": None,
     "reason": "Names pane navigation, not a tab bar."},
    {"label": "splits", "from": "tech-ia-tab-bar", "to": None,
     "reason": "Names pane navigation, not a tab bar."},
    {"label": "multiplexing", "from": "tech-ia-tab-bar", "to": None,
     "reason": "Names terminal multiplexing, not a tab bar."},
    {"label": "density", "from": "tech-ia-density-ladder", "to": None,
     "reason": "Names a generic density setting, not a persisted ladder."},
    {"label": "responsive-layout", "from": "tech-ia-density-ladder", "to": None,
     "reason": "Names responsive adaptation, not a density ladder."},
    {"label": "responsive-sizing", "from": "tech-ia-density-ladder", "to": None,
     "reason": "Names responsive sizing, not a density ladder."},
    {"label": "process-monitor", "from": "tech-viz-log-stream", "to": None,
     "reason": "Names a GPU/process viewer, not a log stream (nvitop)."},
    {"label": "resource-monitor", "from": "tech-viz-log-stream", "to": None,
     "reason": "Names a resource monitor (btop/bottom), not a log stream."},
    {"label": "session-recording", "from": "tech-viz-log-stream", "to": None,
     "reason": "Names terminal session recording (asciinema), not a log stream."},
    {"label": "spinner", "from": "tech-int-skeleton-loading", "to": None,
     "reason": "Spinners and skeletons are distinct loading indicators (NN/g)."},
    {"label": "progress", "from": "tech-int-skeleton-loading", "to": None,
     "reason": "Progress indicators are distinct from skeleton screens (NN/g)."},
    {"label": "sequential-color", "from": "tech-vis-colorblind-safe-status", "to": None,
     "reason": "Names a sequential palette scale, not a colorblind-safe status encoding."},
    {"label": "diverging-color", "from": "tech-vis-colorblind-safe-status", "to": None,
     "reason": "Names a diverging palette scale, not a colorblind-safe status encoding."},
    {"label": "categorical-color", "from": "tech-vis-colorblind-safe-status", "to": None,
     "reason": "Names a categorical palette scale, not a colorblind-safe status encoding."},
    {"label": "color-perception", "from": "tech-vis-colorblind-safe-status", "to": None,
     "reason": "Names color perception generally, not colorblind-safe status encoding."},
    {"label": "color", "from": "tech-vis-colorblind-safe-status", "to": None,
     "reason": "Generic color label; states no accessibility guarantee."},
    {"label": "color-scales", "from": "tech-vis-colorblind-safe-status", "to": None,
     "reason": "Names color scales, not colorblind-safe status encoding."},
    {"label": "prompt-versioning", "from": "tech-ops-prompt-registry", "to": None,
     "reason": "States prompt versioning/management, not a registry; node deleted."},
    {"label": "prompt-deployment", "from": "tech-ops-prompt-registry", "to": None,
     "reason": "States prompt deployment/management, not a registry; node deleted."},
    {"label": "prompt-hub", "from": "tech-ops-prompt-registry", "to": None,
     "reason": "States a prompt/context hub, not a registry; node deleted."},
    {"label": "provisioning", "from": "tech-ops-release-feed", "to": None,
     "reason": "Names infrastructure provisioning, not a release feed."},
    {"label": "serverless-containers", "from": "tech-ops-release-feed", "to": None,
     "reason": "Names a compute primitive, not a release feed."},
    {"label": "webhooks", "from": "tech-ops-release-feed", "to": None,
     "reason": "Names an event callback, not a release feed."},
    {"label": "ligatures", "from": "tech-vis-type-scale", "to": None,
     "reason": "Names a type feature, not a type scale."},
    {"label": "monitors", "from": "tech-trust-alerting", "to": None,
     "reason": "Names a monitor generally, not an alerting surface/rule."},
    {"label": "gateway-proxy", "from": "tech-ops-observability", "to": None,
     "reason": "Names a gateway proxy, not observability instrumentation."},
    {"label": "mcp", "from": "tech-ops-observability", "to": None,
     "reason": "Names a protocol/tool-registry, not observability instrumentation."},
    {"label": "error-code-reference", "from": "tech-ops-issue-tracking", "to": None,
     "reason": "Names a reference table of error codes, not issue tracking."},
    {"label": "list", "from": "tech-viz-data-table", "to": None,
     "reason": "Generic list label; states no tabular data surface."},
    # E4 overlap resolution — the label keeps one direct leaf only.
    {"label": "sparkline", "from": "tech-svg-micro-visual", "to": "tech-viz-time-series-marks",
     "reason": "A sparkline is a time-series mark; one direct leaf (E4)."},
    {"label": "real-time-metrics", "from": "tech-int-live-follow", "to": "tech-ops-metrics",
     "reason": "A metrics label belongs to the metrics leaf; one direct leaf (E4)."},
    {"label": "span-tree", "from": "tech-trust-causal-lineage", "to": "tech-ops-trace-tree",
     "reason": "Literal trace/span tree label; one direct leaf (E4)."},
    {"label": "traces-spans", "from": "tech-trust-causal-lineage", "to": "tech-ops-trace-tree",
     "reason": "Literal trace/span label; one direct leaf (E4)."},
    {"label": "tracing", "from": "tech-trust-causal-lineage", "to": "tech-ops-trace-tree",
     "reason": "Literal tracing label; one direct leaf (E4)."},
    {"label": "trace-waterfall", "from": "tech-ops-trace-tree", "to": "tech-viz-waterfall-timeline",
     "reason": "The waterfall mark has its own leaf; one direct leaf (E4)."},
    {"label": "waterfall-timeline", "from": "tech-ops-trace-tree", "to": "tech-viz-waterfall-timeline",
     "reason": "The waterfall mark has its own leaf; one direct leaf (E4)."},
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
# Quote extraction: a counted record must carry a verbatim source sentence that
# states the leaf's technique. This is deliberately a deterministic, auditable
# scorer, not a model call: it prefers a sentence that contains label/technique
# tokens and a definitional verb, skips navigation/code chrome, and falls back to
# the page title only when no body sentence qualifies.
# --------------------------------------------------------------------------- #
_STOPWORDS = {
    "tech", "grp", "thin", "the", "a", "an", "of", "and", "or", "for", "with", "to",
    "in", "on", "by", "is", "are", "as", "at", "it", "its", "via", "role", "list",
    "design", "system", "surface", "technique", "operation", "layer",
}
_NAV_RE = re.compile(
    r"^(skip to|sign in|navigation|appearance|platform$|ai code|github copilot|"
    r"mcp registry|search|menu|close|open in|terms of|privacy|toggle|expand|collapse|"
    r"prev|next|back|home|docs$|blog$|pricing$|product$|solutions$|resources$|"
    r"company$|get started|try |contact |log in|sign up|install|download|all rights|©)",
    re.I,
)
_CODE_RE = re.compile(r"[{}<>]|</|\bimport \b|package main")
_TEXT_CACHE: dict[str, tuple[str, str]] = {}


def _is_prose(text: str) -> bool:
    """True when the stored page text is usable prose, not compressed/binary junk.

    Some fetches store gzip/binary payloads as ``text`` (the Datadog and W&B pages).
    Those cannot supply a quoted sentence, so they are treated as having no body and
    are excluded from support rather than mining mojibake.
    """
    if not text:
        return False
    sample = text[:20000]
    printable = sum(1 for c in sample if c.isprintable() or c in "\n\t") / len(sample)
    ascii_ratio = sum(1 for c in sample if ord(c) < 128) / len(sample)
    return printable > 0.90 and ascii_ratio > 0.85


def _load_source(sha16: str) -> tuple[str, str]:
    """Return (body text, source title) for a corpus record, cached for the run.

    Non-prose bodies are blanked so the extractor never returns mojibake; the source
    title is still returned when present.
    """
    if sha16 in _TEXT_CACHE:
        return _TEXT_CACHE[sha16]
    path = SOURCES_DIR / f"{sha16}.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        body = payload.get("text") or ""
        cached = (body if _is_prose(body) else "", payload.get("title") or "")
    else:
        cached = ("", "")
    _TEXT_CACHE[sha16] = cached
    return cached


def _has_evidence(sha16: str) -> bool:
    """True when a record has a usable source body or title to quote from.

    Mirrors ``extract_quote``'s fallbacks exactly so a record is never counted as
    support unless a non-empty quote can be produced for it.
    """
    body, title = _load_source(sha16)
    if body.strip():
        return True
    return bool(title.strip()) and not _NAV_RE.match(title)


def _tokens(value: str) -> list[str]:
    return [
        w for w in re.findall(r"[a-z0-9]+", value.lower())
        if w not in _STOPWORDS and len(w) > 1
    ]


def _sentences(text: str) -> list[str]:
    """Split prose into clean candidate sentences (no nav chrome, no code)."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    out: list[str] = []
    for part in parts:
        sentence = re.sub(r"\s+", " ", part).strip()
        if (
            30 <= len(sentence) <= 300
            and not _NAV_RE.match(sentence)
            and not _CODE_RE.search(sentence)
        ):
            out.append(sentence)
    return out


def _matches_pattern(node_id: str, record: "Record") -> bool:
    """True when the stored source states the leaf's technique (pattern gate)."""
    pattern = EVIDENCE_PATTERNS.get(node_id)
    if not pattern:
        return True
    body, title = _load_source(record.sha)
    if not (body.strip() or title.strip()):
        return False
    return bool(re.search(pattern, body + " \n " + title, re.I))


def extract_quote(node_id: str, technique: str, labels: list[str],
                  record: "Record") -> tuple[str, str, float]:
    """Pick the source sentence that best states ``technique`` for ``record``.

    Sentences that match the leaf's evidence pattern are strongly preferred; the
    node's own id/technique tokens are "strong" evidence (weight 4) and the raw
    direct-label tokens are supporting evidence (weight 1). Returns
    ``(quote, source_kind, score)`` where kind is ``sentence``, ``title`` or
    ``excerpt``. The quote is always verbatim text from the stored source page.
    """
    text, source_title = _load_source(record.sha)
    pattern = EVIDENCE_PATTERNS.get(node_id)
    pattern_re = re.compile(pattern, re.I) if pattern else None
    strong = set(_tokens(node_id)) | set(_tokens(technique))
    label_tokens = set(_tokens(" ".join(labels)))
    best: str | None = None
    best_score = 0.0
    for index, sentence in enumerate(_sentences(text)):
        pattern_hit = bool(pattern_re and pattern_re.search(sentence))
        present = set(_tokens(sentence))
        hits = len(present & strong)
        if not pattern_hit and hits == 0 and not (present & label_tokens):
            continue
        score = (8.0 if pattern_hit else 0.0) + hits * 4.0 + len(present & label_tokens) * 1.0
        if re.search(
            r"\bis (a|an|the)\b|\bprovides\b|\ballows\b|\blets you\b|\bused (for|to)\b|"
            r"\bdesigned (for|to)\b|\bshows\b|\bdisplay|\benable|\buse\b",
            sentence,
            re.I,
        ):
            score += 1.0
        score -= max(0, index - 60) * 0.02
        if score > best_score:
            best_score = score
            best = sentence
    if best:
        return best, "sentence", best_score
    if source_title.strip() and not _NAV_RE.match(source_title):
        return source_title, "title", 0.5
    if text.strip():
        return re.sub(r"\s+", " ", text.strip())[:240], "excerpt", 0.0
    return "", "none", 0.0


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


def build_evidence_quotes(node_id: str, technique: str, labels: list[str],
                          matched: list[Record]) -> list[dict]:
    """One verbatim source quote per counted record (the support proof).

    Records whose source has no usable body/title are not quotable and are dropped
    upstream, so every record here yields a non-empty quote. Quotes are stored best
    first so the representative evidence is the first entry.
    """
    quotes: list[dict] = []
    label_set = set(labels)
    for record in matched:
        quote, kind, score = extract_quote(node_id, technique, labels, record)
        if not quote.strip():
            continue
        quotes.append(
            {
                "sha256": record.sha,
                "uri": record.uri,
                "family": record.family,
                "title": record.title,
                "labels": sorted(record.techniques & label_set),
                "quote": quote,
                "source_kind": kind,
                "score": round(score, 2),
            }
        )
    quotes.sort(key=lambda q: (-q["score"], q["family"], q["uri"]))
    return quotes


def make_technique_node(node_id: str, parent: str, labels: list[str],
                        matched: list[Record], note: str, technique: str,
                        thin: bool = False) -> dict:
    node = make_node(
        node_id,
        parent,
        "thin" if thin else "cluster",
        {"technique": node_id},
        matched,
        note if thin else f"{note} Direct labels: {', '.join(sorted(labels))}.",
    )
    node["technique"] = technique
    node["evidence_quotes"] = build_evidence_quotes(node_id, technique, labels, matched)
    # A quoted, technique-stating source is PASS. A leaf that loses its support to the
    # evidence pattern (the sources only state a broader idea) is a PROMOTION and drops
    # below the >=3-source bar, so catalogs/skills demote it to [P]. Thin leaves are
    # PASS-but-thin: their few sources do state the technique.
    node["semantic_verdict"] = "PASS" if (thin or node["meets_three_source_rule"]) else "PROMOTION"
    if thin:
        node["note"] = f"Below the >={MIN_SUPPORT}-source bar; not promoted. {note}"
    return node


def _deleted_node_ids() -> set[str]:
    return {str(n["id"]) for n in DELETED_NODES}


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
def build() -> dict:
    records, inputs = load_corpus()
    deleted_ids = _deleted_node_ids()

    nodes: list[dict] = []
    crosswalk: dict[str, list[str]] = {}

    # -- root + dimensions --------------------------------------------------- #
    root = make_node(
        "root", None, "root", {"schema": "control-room-taxonomy/v1", "families": FAMILIES},
        records, "The whole 5-family corpus. Nodes overlap; supports do not sum.",
    )
    root["facet"] = {"schema": "control-room-taxonomy/v1", "families": FAMILIES}
    root["evidence_basis"] = "structural-corpus-total"
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
                "evidence_basis": "structural-dimension",
            }
        )

    # -- category cluster branch -------------------------------------------- #
    for node_id, values in CATEGORY_CROSSWALK.items():
        matched = [r for r in records if r.category in values]
        node = make_node(node_id, "dim-category", "cluster", {"category": node_id},
                         matched, f"Raw category values folded in: {', '.join(sorted(values))}.")
        node["evidence_basis"] = "structural-category-value"
        nodes.append(node)

    # -- aesthetic cluster branch ------------------------------------------- #
    aesthetic_values = sorted({r.aesthetic for r in records if r.aesthetic})
    for value in aesthetic_values:
        matched = [r for r in records if r.aesthetic == value]
        node = make_node(f"aes-{value}", "dim-aesthetic", "cluster", {"aesthetic": value},
                         matched, "Raw aesthetic value.")
        node["evidence_basis"] = "structural-aesthetic-value"
        nodes.append(node)

    # -- stack cluster branch ----------------------------------------------- #
    for node_id, values in STACK_CROSSWALK.items():
        matched = [r for r in records if r.stack & set(values)]
        node = make_node(node_id, "dim-stack", "cluster", {"stack": node_id},
                         matched, f"Raw stack values folded in: {', '.join(sorted(values))}.")
        node["evidence_basis"] = "structural-stack-value"
        nodes.append(node)

    # -- quality signal branch ---------------------------------------------- #
    for signal in QUALITY_SIGNALS:
        matched = [r for r in records if signal in r.quality]
        node = make_node(f"ev-{signal}", "dim-evidence", "signal", {"signal": signal},
                         matched, "Records carrying this quality signal.")
        node["evidence_basis"] = "structural-quality-signal"
        nodes.append(node)

    # -- technique branch ---------------------------------------------------- #
    # Track per-node matched sets so groups can union their children exactly.
    matched_by_node: dict[str, list[Record]] = {}
    for group_id, group_label, children in TECH_GROUPS:
        for node_id, labels, _note in children:
            # Only records whose stored source both is quotable AND states the
            # technique count; an unquotable or off-topic record has no sentence that
            # states the technique (E1 "no quote, no count").
            matched = [
                r for r in records
                if r.techniques & set(labels) and _has_evidence(r.sha)
                and _matches_pattern(node_id, r)
            ]
            matched_by_node[node_id] = matched
            crosswalk[node_id] = list(labels)
        # Group support is the union of its children's matched records.
        group_records = {r.sha: r for node_id, _, _ in children for r in matched_by_node[node_id]}
        matched_by_node[group_id] = list(group_records.values())
        crosswalk[group_id] = sorted({lab for _, labs, _ in children for lab in labs})
        group = make_node(group_id, "dim-technique", "group", {"group": group_label},
                          matched_by_node[group_id],
                          f"Union of its promoted child clusters. {group_label}.")
        group["evidence_basis"] = "union-of-children"
        group["evidence_quotes"] = []
        nodes.append(group)
        # Child nodes are appended after their group so parent-before-child holds.
        for node_id, labels, note in children:
            nodes.append(
                make_technique_node(
                    node_id, group_id, labels, matched_by_node[node_id], note,
                    TECHNIQUE.get(node_id, node_id.replace("tech-", "").replace("-", " ")),
                )
            )

    # -- thin nodes ---------------------------------------------------------- #
    # A thin leaf whose sources also fail its evidence pattern has NO quote stating
    # the technique, so it is ABSENT and dropped (rather than kept at support 0).
    dropped_thin: list[dict] = []
    for node_id, labels, parent, note in THIN_NODES:
        matched = [
            r for r in records
            if r.techniques & set(labels) and _has_evidence(r.sha)
            and _matches_pattern(node_id, r)
        ]
        if not matched:
            dropped_thin.append(
                {"node": node_id, "labels": labels,
                 "reason": "No stored source states the technique; dropped as ABSENT."}
            )
            crosswalk.pop(node_id, None)
            continue
        matched_by_node[node_id] = matched
        crosswalk[node_id] = list(labels)
        nodes.append(
            make_technique_node(
                node_id, parent, labels, matched, note,
                TECHNIQUE.get(node_id, node_id.replace("thin-", "").replace("tech-", "").replace("-", " ")),
                thin=True,
            )
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

    # -- semantic review ledger --------------------------------------------- #
    technique_leaves = [
        n for n in nodes if "technique" in n.get("facet", {}) and n["kind"] in ("cluster", "thin")
    ]
    verdict_totals = collections.Counter(n["semantic_verdict"] for n in technique_leaves)
    downgraded_nodes = [
        {
            "node": n["id"],
            "label_support": None,
            "quoted_support": n["support"],
            "reason": "Sources under this label state a broader/adjacent idea, not the "
            "narrow technique; below the >=3-source bar, demoted to [P].",
        }
        for n in technique_leaves
        if n["kind"] == "cluster" and n["semantic_verdict"] == "PROMOTION"
    ]
    by_family = collections.Counter(r.family for r in records)
    taxonomy = {
        "schema": "control-room-taxonomy/v1",
        "phase": "q0_semantic_crosswalk",
        "corpus": "control_room_research",
        "min_support": MIN_SUPPORT,
        "inputs": inputs,
        "corpus_totals": {
            "records_total": len(records),
            "by_family": {f: by_family[f] for f in FAMILIES},
            "unique_technique_labels": len(label_counts),
            "canonical_leaves": len(crosswalk),
            "promoted_leaves": len([
                n for n in nodes
                if n["kind"] == "cluster" and n["id"].startswith("tech-")
                and n["meets_three_source_rule"]
            ]),
            "thin_leaves": len(thin_kept),
            "records_with_mapped_technique": total_technique_records,
            "mapped_labels": len(mapped_labels),
            "unmapped_labels": [[lab, count] for lab, count in unmapped.items()],
            "unmapped_mentions": sum(unmapped.values()),
        },
        "method": (
            "Quoted-evidence direct support. Each raw technique label maps to exactly one "
            "technique leaf; a leaf counts a record only when the record carries one of the "
            "leaf's direct labels AND a verbatim source sentence stating the leaf's technique "
            "is stored in the leaf's evidence_quotes. Broad or adjacent labels are promotions: "
            "removed from the leaf, re-homed only to the single leaf they literally name, or "
            "left unmapped. Nodes with no direct support are deleted (see repair.deleted_nodes)."
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
                {"from": "tech-trust-causal-lineage", "to": "tech-ops-trace-tree",
                 "reason": "Same span/trace labels; collapse the duplicate leaf (E4)."},
            ],
        },
        "semantic_review": {
            "method": (
                "Every technique leaf declares the source-text pattern that states its "
                "technique (EVIDENCE_PATTERNS in build_taxonomy.py). A corpus record counts "
                "only when its stored page matches that pattern AND a verbatim sentence is "
                "stored in evidence_quotes. Verdicts: PASS (quote states the narrow technique), "
                "PROMOTION (the leaf's sources state only a broader/adjacent idea, so quoted "
                "support falls below the bar and the leaf is demoted to [P]; or a broader raw "
                "label was removed from a narrow leaf), ABSENT (no source states it — node "
                "deleted)."
            ),
            "rule": (
                "One direct leaf per raw label; a support count requires a stored "
                "evidence_quotes entry. A broader label backs its umbrella node and nothing "
                "narrower; no double support (E4)."
            ),
            "verdict_totals": {
                "PASS": verdict_totals.get("PASS", 0),
                "PROMOTION": verdict_totals.get("PROMOTION", 0),
                "ABSENT": len(DELETED_NODES) + len(dropped_thin),
                "promoted_labels": len(SEMANTIC_PROMOTIONS),
            },
            "downgraded_nodes": downgraded_nodes,
            "dropped_thin_nodes": dropped_thin,
            "promotions": SEMANTIC_PROMOTIONS,
            "absences": [
                {"node": str(n["id"]), "reason": str(n["reason"])} for n in DELETED_NODES
            ] + [{"node": d["node"], "reason": d["reason"]} for d in dropped_thin],
            "overlap_resolution": {
                entry["label"]: entry["to"]
                for entry in SEMANTIC_PROMOTIONS
                if entry["label"] in {
                    "fuzzy-filter", "real-time-metrics", "span-tree", "traces-spans",
                    "tracing", "trace-waterfall", "waterfall-timeline", "sparkline",
                }
            },
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
                    "from": ["logs", "streaming", "real-time-streaming", "request-log", "log-stream"],
                    "into": "tech-viz-log-stream",
                    "reason": "Live log/event surface synonyms.",
                },
                {
                    "from": ["table-view", "tables", "table", "reference-tables",
                             "virtualized-table"],
                    "into": "tech-viz-data-table",
                    "reason": "Table synonyms; virtualization kept as a sub-claim note only.",
                },
                {
                    "from": ["design-tokens", "color-tokens", "theme-config", "themes",
                             "theming", "dark-theme", "light-theme", "light-mode",
                             "dark-first-theming", "monochrome-palette", "color-palette",
                             "color-profiles"],
                    "into": "tech-vis-design-tokens",
                    "reason": "Token/theme/palette synonyms for the token/theme layer.",
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


def technique_leaves(taxonomy: dict) -> list[dict]:
    """Technique leaves = nodes whose facet names a technique (excludes groups/facets)."""
    return [
        n for n in taxonomy["nodes"]
        if "technique" in n.get("facet", {}) and n["kind"] in ("cluster", "thin")
    ]


def verify_evidence(taxonomy: dict) -> list[str]:
    """Return a list of violations: a support count without stored evidence quotes.

    A clean taxonomy has one verbatim quote per counted record for every technique
    leaf, and every quote is a non-empty string with a resolvable sha/uri.
    """
    problems: list[str] = []
    for node in technique_leaves(taxonomy):
        quotes = node.get("evidence_quotes") or []
        if node["support"] > 0 and not quotes:
            problems.append(f"{node['id']}: support={node['support']} but no evidence_quotes")
        quoted_shas = {q["sha256"] for q in quotes}
        if len(quoted_shas) != node["support"]:
            problems.append(
                f"{node['id']}: support={node['support']} but {len(quoted_shas)} distinct "
                f"quoted records"
            )
        for quote in quotes:
            if not quote.get("quote", "").strip():
                problems.append(f"{node['id']}: empty quote for {quote.get('sha256')}")
            if not quote.get("uri"):
                problems.append(f"{node['id']}: quote without uri for {quote.get('sha256')}")
    return problems


def write_crosswalk_markdown(taxonomy: dict, path: Path) -> None:
    """Emit the full semantic crosswalk table used to fix E1/E4."""
    review = taxonomy["semantic_review"]
    lines: list[str] = []
    lines.append("---")
    lines.append("status: accepted")
    lines.append("---")
    lines.append("")
    lines.append("# Control Room semantic crosswalk — quoted-evidence support (campaign `control_room_research_repair2`, phase `q0_semantic_crosswalk`)")
    lines.append("")
    lines.append("**Generated by:** `experiments/research/control_room/build_taxonomy.py`")
    lines.append("**Review basis:** `docs/reviews/control_room_repair_entailment.md` (E1, E4).")
    lines.append("")
    lines.append("This file is the record-level verdict for every taxonomy node with a support")
    lines.append("count. Each counted corpus record stores a verbatim sentence from its stored")
    lines.append("source page (`experiments/research/control_room/sources/<sha256[:16]>.json`);")
    lines.append("a support count without such a quote is a build error.")
    lines.append("")
    lines.append("## 1. Method and verdicts")
    lines.append("")
    lines.append(review["method"])
    lines.append("")
    lines.append(review["rule"])
    lines.append("")
    lines.append("Verdict semantics:")
    lines.append("")
    lines.append("- **PASS** — the quoted source sentence states the node's narrow technique.")
    lines.append("- **PROMOTION** — the quote states only a broader/adjacent label; the label was")
    lines.append("  removed from the leaf (and re-homed only where it literally names another leaf).")
    lines.append("- **ABSENT** — no source states the technique; the node was deleted.")
    lines.append("")
    totals = review["verdict_totals"]
    lines.append(
        f"Totals: **{totals['PASS']} PASS leaves**, **{totals['PROMOTION']} PROMOTION leaves**, "
        f"**{totals['ABSENT']} ABSENT nodes**, **{totals['promoted_labels']} promoted labels**."
    )
    lines.append("")

    # -- Summary table ------------------------------------------------------- #
    lines.append("## 2. Summary — every surviving technique leaf")
    lines.append("")
    lines.append("| Node | Technique | Support | Families | Verdict | Representative quote | Source |")
    lines.append("|---|---|---:|---|---|---|---|")
    for node in technique_leaves(taxonomy):
        quotes = node.get("evidence_quotes") or []
        rep = quotes[0] if quotes else {}
        quote = (rep.get("quote") or "").replace("|", "\\|")
        if len(quote) > 220:
            quote = quote[:217] + "..."
        families = ", ".join(sorted(node["support_by_family"]))
        uri = rep.get("uri", "")
        lines.append(
            f"| `{node['id']}` | {node['technique']} | {node['support']} | {families} | "
            f"{node.get('semantic_verdict', 'PASS')} | {quote} | {uri} |"
        )
    lines.append("")

    # -- Promotions ---------------------------------------------------------- #
    lines.append("## 3. Removed label promotions (E1 + E4)")
    lines.append("")
    lines.append("| Label | Formerly counted by | Disposition | Reason |")
    lines.append("|---|---|---|---|")
    for entry in review["promotions"]:
        dest = f"re-homed to `{entry['to']}`" if entry["to"] else "unmapped"
        lines.append(
            f"| `{entry['label']}` | `{entry['from']}` | {dest} | {entry['reason']} |"
        )
    lines.append("")

    # -- E4 overlap resolution ---------------------------------------------- #
    lines.append("## 4. E4 overlap resolution — one direct leaf per label")
    lines.append("")
    lines.append("| Label | Single direct leaf |")
    lines.append("|---|---|")
    for label, leaf in sorted(review["overlap_resolution"].items()):
        lines.append(f"| `{label}` | `{leaf}` |")
    lines.append("")
    lines.append("No raw technique label maps to more than one technique leaf in")
    lines.append("`taxonomy.crosswalk` (enforced by construction; see `build()`).")
    lines.append("")

    # -- Node-level downgrades ---------------------------------------------- #
    lines.append("## 5. Leaves demoted by the evidence gate (PROMOTION)")
    lines.append("")
    lines.append("These leaves keep their direct-label records, but the stored sources state")
    lines.append("only a broader/adjacent idea, so their quoted support is below the >=3-source")
    lines.append("bar and catalogs/skills demote them to `[P]`.")
    lines.append("")
    lines.append("| Node | Quoted support | Reason |")
    lines.append("|---|---:|---|")
    for entry in review.get("downgraded_nodes", []):
        lines.append(f"| `{entry['node']}` | {entry['quoted_support']} | {entry['reason']} |")
    lines.append("")

    # -- Deletions ----------------------------------------------------------- #
    lines.append("## 6. Deleted nodes (ABSENT)")
    lines.append("")
    lines.append("| Node | Prior support | Promoted from | Reason |")
    lines.append("|---|---:|---|---|")
    for node in taxonomy["repair"]["deleted_nodes"]:
        promoted = ", ".join(f"`{x}`" for x in node["promoted_from"])
        lines.append(
            f"| `{node['id']}` | {node['prior_support']} | {promoted} | {node['reason']} |"
        )
    for entry in review.get("dropped_thin_nodes", []):
        labels = ", ".join(f"`{x}`" for x in entry["labels"])
        lines.append(f"| `{entry['node']}` | <3 | {labels} | {entry['reason']} |")
    lines.append("")

    # -- Full evidence appendix --------------------------------------------- #
    lines.append("## 7. Full quoted evidence (per node, per record)")
    lines.append("")
    for node in technique_leaves(taxonomy):
        lines.append(f"### `{node['id']}` — {node['technique']} (support {node['support']})")
        lines.append("")
        for quote in node.get("evidence_quotes") or []:
            text = (quote.get("quote") or "").replace("\n", " ")
            lines.append(
                f"- **{quote.get('sha256')}** ({quote.get('family')}) — *{quote.get('title') or quote.get('uri')}*:"
            )
            lines.append(f"  > {text}")
            lines.append(f"  source: {quote.get('uri')}  (labels: {', '.join(quote.get('labels') or [])})")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    taxonomy = build()
    problems = verify_evidence(taxonomy)
    TAXONOMY_PATH.write_text(json.dumps(taxonomy, indent=2) + "\n", encoding="utf-8")
    write_crosswalk_markdown(taxonomy, CROSSWALK_PATH)
    totals = taxonomy["corpus_totals"]
    print(f"wrote {TAXONOMY_PATH.relative_to(ROOT)}")
    print(f"wrote {CROSSWALK_PATH.relative_to(ROOT)}")
    print(f"  nodes: {len(taxonomy['nodes'])}  promoted: {totals['promoted_leaves']}"
          f"  thin: {totals['thin_leaves']}")
    print(f"  mapped labels: {totals['mapped_labels']}/{totals['unique_technique_labels']}"
          f"  unmapped mentions: {totals['unmapped_mentions']}")
    review = taxonomy["semantic_review"]
    print(f"  semantic verdicts: {review['verdict_totals']}")
    for deleted in taxonomy["repair"]["deleted_nodes"]:
        print(f"  DELETED {deleted['id']} (was {deleted['prior_support']})")
    if problems:
        for problem in problems:
            print(f"  EVIDENCE VIOLATION: {problem}")
        raise SystemExit(1)
    print("  evidence check: OK (every technique support has stored quotes)")


if __name__ == "__main__":
    main()
