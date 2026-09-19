# Control Room render gate

**Status:** PASS
**Classes:** navigation · loading · degraded · scrolling · keyboard (the restored served boards) · legacy parked: geometry/semantics (IA §10.3/§10) · charts · visuals · style · a11y · feature-parity (u5) · live IA-core · interactions
**Requested classes:** navigation, loading, degraded, scrolling, keyboard
**Executed classes:** navigation, loading, degraded, scrolling, keyboard
**Omitted classes:** none
**Fixtures:** boards (restored) + F-0..F-7 (legacy parked; deterministic, no live Redis/clock/network — waiver W2)
**Viewports exercised:** desktop, narrow
**Themes exercised:** dark, light
**Coverage executed:** navigation: seven destinations, exactly one visible board, aria-current, no horizontal overflow, every board captured (desktop dark+light, narrow dark) · loading: first visit and reload for Operations/Surfaces/Routing; each endpoint requested exactly once; rendered fixture values asserted; delayed and failed routing responses settle (loading state refused by the readiness predicate) · degraded: an unreadable control db reads 'unavailable', never 0; a failed read model names its reason and URL while its siblings render · scrolling: real wheel input reaches the last below-fold run row; an overflow-y:hidden page fails the same check · keyboard: Enter opens the run drawer with focus on its close control; Escape closes it and returns focus to the originating row; the loaded drawer renders the run-inspection blocks (measured-zero and unknown cost provenance, independent verification separate from the agent's claim, delivered-knowledge ids, the prepared-step reference, an unknown-state timing), and a 200 error envelope renders by name
**Coverage omitted:** mobile viewport (390x844), forced-colors theme, WCAG-AA contrast, first-paint timing, charts, visuals, style, a11y, parity, live, interactions (legacy parked classes)
**Candidate:** ca1ef46dc (verified against the checkout HEAD)

**Screenshots:** 21 (boards-degraded 1, boards-keyboard 2, boards-loading 1, boards-navigation 17)

No violations.

## Captures

- `/tmp/wt_run_evidence/apps/control_room/verification/boards_fleet_desktop_dark_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_status_desktop_dark_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_flags_desktop_dark_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_sessions_desktop_dark_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_routing_desktop_dark_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_operations_desktop_dark_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_surfaces_desktop_dark_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_fleet_desktop_light_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_status_desktop_light_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_flags_desktop_light_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_sessions_desktop_light_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_routing_desktop_light_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_operations_desktop_light_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_surfaces_desktop_light_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_routing_narrow_dark_1024x768.png` — boards-navigation/narrow
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_operations_narrow_dark_1024x768.png` — boards-navigation/narrow
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_surfaces_narrow_dark_1024x768.png` — boards-navigation/narrow
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_loading_operations_reload_desktop_dark_1440x900.png` — boards-loading/desktop
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_degraded_operations_desktop_dark_1440x900.png` — boards-degraded/desktop
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_keyboard_drawer_dark_1440x900.png` — boards-keyboard/desktop
- `/tmp/wt_run_evidence/apps/control_room/verification/boards_keyboard_drawer_light_1440x900.png` — boards-keyboard/desktop
