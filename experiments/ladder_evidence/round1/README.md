# flash-exploration ladder evidence — round 1 (frozen review input)

Commit-frozen copy of the round-1 ladder evidence so a review cell can read it at
`/repo/experiments/ladder_evidence/round1/` (cells cannot reliably see the live
`experiments/results` bind nor host `/tmp` staging). Contents: the score artifact and,
per cell, the record + the generated `taskman` sources (any layout).

- ladder base: 121126dfbcd65a656883e3f3cc81b12e612aeeeb
- scorer: scripts/score_flash_ladder.py (ladder-cells/v1)
- pristine contract test at base: tests/flash_ladder/taskman_contract_test.py
