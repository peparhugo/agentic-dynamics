# Control Room render gate

**Status:** PASS
**Classes:** navigation · loading · degraded · scrolling · keyboard (the restored served boards) · legacy parked: geometry/semantics (IA §10.3/§10) · charts · visuals · style · a11y · feature-parity (u5) · live IA-core · interactions
**Requested classes:** navigation, loading, degraded, scrolling, keyboard
**Executed classes:** navigation, loading, degraded, scrolling, keyboard
**Omitted classes:** none
**Fixtures:** boards (restored) + F-0..F-7 (legacy parked; deterministic, no live Redis/clock/network — waiver W2)
**Viewports:** desktop 1440x900, narrow 1024x768, mobile 390x844
**Themes:** dark, light, forced-colors
**Primitives:** present/unique · in-viewport · non-zero box · scrollable pages (vertical) · no horizontal overflow · WCAG-AA contrast · first-paint · console-clean
**Candidate:** b89210424 (verified against the checkout HEAD)

**Screenshots:** 21 (boards-degraded 1, boards-keyboard 2, boards-loading 1, boards-navigation 17)

No violations.

## Captures

- `/tmp/wt_cr_followups/apps/control_room/verification/boards_fleet_desktop_dark_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_status_desktop_dark_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_flags_desktop_dark_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_sessions_desktop_dark_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_routing_desktop_dark_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_operations_desktop_dark_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_surfaces_desktop_dark_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_fleet_desktop_light_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_status_desktop_light_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_flags_desktop_light_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_sessions_desktop_light_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_routing_desktop_light_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_operations_desktop_light_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_surfaces_desktop_light_1440x900.png` — boards-navigation/desktop
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_routing_narrow_dark_1024x768.png` — boards-navigation/narrow
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_operations_narrow_dark_1024x768.png` — boards-navigation/narrow
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_surfaces_narrow_dark_1024x768.png` — boards-navigation/narrow
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_loading_operations_reload_desktop_dark_1440x900.png` — boards-loading/desktop
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_degraded_operations_desktop_dark_1440x900.png` — boards-degraded/desktop
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_keyboard_drawer_dark_1440x900.png` — boards-keyboard/desktop
- `/tmp/wt_cr_followups/apps/control_room/verification/boards_keyboard_drawer_light_1440x900.png` — boards-keyboard/desktop
