# Δ-entropy instrument — corpus measurement

schema `delta_entropy/v1` · generated 2026-08-30T19:04:30Z
ΔH threshold: `0.0` ([P] sign-of-delta (design leaves the cut unspecified))

## Coverage (exact — never imputed)

- story cells measured: 235
- campaign cells measured: 86
- test-join complete: 126
- test-join incomplete (ΔH measured, quadrant FAILED-finding): 195
- clean-but-wrong count (the 2d/2e wall): 1

## Quadrant distribution (joined cells only)

- clean_and_right: 5
- clean_but_wrong: 1
- messy_and_broken: 21
- messy_but_right: 99

## Per-model quadrant distribution

- campaign: {'messy_but_right': 52, 'messy_and_broken': 16, 'clean_and_right': 4}
- claude-haiku-4-5: {'messy_but_right': 20, 'messy_and_broken': 3, 'clean_but_wrong': 1}
- claude-sonnet-5: {'messy_but_right': 5}
- deepseek-v4-flash: {'messy_but_right': 3}
- deepseek-v4-pro: {'messy_but_right': 7}
- gpt-5.6-luna: {'clean_and_right': 1, 'messy_but_right': 4}
- gpt-5.6-sol: {'messy_but_right': 6}
- gpt-5.6-terra: {'messy_and_broken': 2, 'messy_but_right': 2}

## Skipped cells

- 09834db35c9e: baseline_missing
- 2b6d8dd557e9: baseline_missing
- 51662084171e: baseline_missing
- 591e2dc25d1f: baseline_missing
- 7b38e1d32d59: baseline_missing
- 9cd288645b5f: baseline_missing
- f0796e72c54d: baseline_missing
- c0e0d6871f69: baseline_missing
- f488d141c683: baseline_missing
