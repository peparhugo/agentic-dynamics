# Architecture Visual

## Purpose

`admin/static/architecture.svg` is the source asset for **The information-acquisition machine**. It binds the Operational Framework's golden circle to the engineering loop without introducing a measured numerical claim.

The thesis is: ledger events expose the unmeasured gap; measurement turns events into information; information is required before a policy can be written; policy becomes useful when it is tested as an arm in a grid and revised through a campaign.

## Concept Bindings

| Territory | System stages | Operational meaning |
|---|---|---|
| WHY, solid amber core | `ledger -> measure -> information` | Measured information should become testable policy. Events alone are not decision rules. |
| HOW, double cyan boundary | `ExperimentSpec -> DAG -> cells -> jobs -> attempts -> ledger -> measure` | The instrument creates an evidence surface and exposes the cost levers `C0`, `P`, `e`, `r`, `beta`, and `EPM` to reversible calculator scenarios. |
| WHAT, dashed sky boundary | `policy -> grid -> campaign -> compare -> adapt` | Policy is treated as an experimental arm. The result informs per-task routing, default architecture, bounded autonomy, and the provider playbook. |

The line treatments are semantic rather than decorative. Solid, double, and dashed boundaries preserve WHY/HOW/WHAT when the asset is printed without color.

## Circuits

The execution and learning loop is:

1. `ExperimentSpec` records the question, workflow, factors, and rules.
2. Compilation produces a dependency-ordered `DAG`.
3. The design materializes into factor-cross-product `CELLS` and queueable `JOBS`.
4. `ATTEMPTS` retain tokens, timing, tools, and outcomes.
5. Attempts emit append-only events into the `LEDGER`.
6. `MEASURE` applies declared measurement rules to derive named `INFORMATION`.
7. `COMPARE` evaluates arm loss across cost, quality, latency, SLA, and value.
8. `ADAPT` changes one variable and closes the loop through the next specification.

The policy branch starts only after information exists:

1. The `requires subset-of produced?` diamond rejects a control rule whose required information is unavailable.
2. `POLICY` consumes produced information to route, retry, escalate, or budget.
3. `GRID` makes policy a factor level rather than an unquestioned default.
4. `CAMPAIGN` repeats the grid and rejoins adaptation.

The lower rail restates the load-bearing order: `INSTRUMENT -> DERIVE -> WRITE POLICY -> GRID -> CAMPAIGN`. Its arrows run right-to-left to align each stage with the circuit node above it. The gate caption, `information first`, marks the only dependency diamond.

## Decision Surfaces

The right-hand dossier binds policy to the page's WHAT material:

- `two-way door`: reversible per-task routing.
- `one-way door`: a default architecture whose effects compound.
- `autonomous door`: a policy may act only inside its declared budget.
- `provider playbook`: route, reserve, and review provider use as explicit operating choices.

The HOW card binds the same machine to the cost model without restating or changing any value. `C0`, `P`, `e`, `r`, `beta`, and `EPM` are variable names, while the calculator is identified as a reversible scenario test.

## Evidence Burden

The two braces use symbolic `N x M` expressions:

- `N linked sessions x M measurement angles = instrumented evidence surface`
- `analysis burden = N x M before cross-arm aggregation`

These expressions explain scaling relationships. They are not observed values and add no page statistic.

## Integration

The SVG is self-contained and uses one root `<svg>`, an internal `<defs>`, internal styles, gradients, markers, accessible `<title>` and `<desc>`, and no external image or JavaScript canvas dependency. To inline it in `firebase/public/framework.html`, place the root `<svg>...</svg>` inside the architecture figure's horizontally scrollable wrapper rather than linking it through `<img>` or `<object>`. This allows the inherited `--bg`, `--bg2`, `--bg3`, `--bg4`, `--b`, `--ba`, `--t`, `--t2`, `--t3`, `--ac`, `--am`, `--cy`, and `--success` tokens to follow the page theme.

The web figure should retain:

- `id="architecture"` on its wrapping `<figure>`.
- A keyboard-focusable overflow wrapper with `tabindex="0"` and an accessible label.
- A minimum SVG width near `900px` below the mobile breakpoint so formal labels remain legible.
- The prescribed caption: `Events are not policy. Measurement creates the information that makes a policy arm writable, comparable, and adaptable.`
- An adjacent ordered text equivalent based on the circuit walkthrough above.

The source includes standalone dark and light fallbacks, a print treatment, and a `prefers-reduced-motion` rule. Two slow path tracers are optional orientation cues; arrowheads and labels carry the complete meaning when animation is disabled.
