# Design QA — Redragon Control S118

- Source visual truth: `/mnt/NVME_Projetos/MouseKeyboard/design/reference-keyboard.png`
- Implementation screenshot: `/mnt/NVME_Projetos/MouseKeyboard/design/implementation-keyboard.png`
- Combined comparison: `/mnt/NVME_Projetos/MouseKeyboard/design/comparison-keyboard.png`
- State: dark theme, K552 page, Principal profile, custom per-key RGB
- Viewport: 1480 × 1050 CSS px, device scale factor 1
- Source pixels: 1487 × 1058; normalized to 1480 × 1050 for comparison
- Implementation pixels: 1480 × 1050

## Full-view comparison evidence

The source and implementation were placed together in one 2960 × 1050 comparison image. The final implementation preserves the source's dark GNOME layout, persistent left navigation, device state in the header, K552-focused hierarchy, full ABNT2 keyboard editor, RGB controls, profile selector and primary apply action. The complete keyboard and the compact horizontal settings panel are visible simultaneously without scrolling.

## Focused comparison evidence

The keyboard editor and lower settings panel were checked as the critical focused regions. The proportional grid fills the editor frame; all rows, the navigation cluster, ABNT2 characters, TKL navigation keys, rainbow progression and card boundaries are visible and readable. The three settings groups fit on one horizontal row. A separate crop was not needed because the equal-size full-view comparison renders labels legibly.

## Required fidelity surfaces

- Fonts and typography: Cantarell/system GNOME typography matches the intended native application; title, section and caption hierarchy remain clear.
- Spacing and layout rhythm: sidebar, page padding, cards and two-column controls follow the source proportions. No content overflows the default window.
- Colors and tokens: near-black canvas, raised charcoal cards, violet selection/action color, green device status and per-key RGB spectrum match the source direction.
- Image and asset fidelity: the source keyboard illustration is represented by the actual interactive key controls rather than a static replacement. GNOME symbolic icons are used consistently.
- Copy and content: Portuguese labels are aligned to the S118/K552 device and the implemented controls.

## Comparison history

1. Initial capture — blocked.
   - P1: the keyboard row exceeded the usable card width and hid Home/PgUp/PgDn.
   - P2: the lower controls were clipped by an undersized default window.
   - Fix: increased the default window to 1480 × 1050, restored readable key dimensions, grouped the page heading and forced the initial scroll position to the top.
2. Compact-key revision — blocked.
   - P1: the keyboard fit but its reduced keys looked visually cramped and unlike the source.
   - Fix: restored 42 px keys and used the larger source-proportioned window.
3. Final capture — passed.
   - Post-fix evidence: `/mnt/NVME_Projetos/MouseKeyboard/design/comparison-keyboard.png` shows the entire keyboard and the main RGB/behavior controls within the intended viewport.
4. User screenshot follow-up — blocked, then passed after revision.
   - P1: the lower settings cards exceeded the viewport and required scrolling.
   - P2: fixed-width keys occupied only part of the editor frame, leaving excessive empty space on the right.
   - Fix: consolidated illumination, intensity and action controls into one horizontal card; moved selection actions into the editor header; replaced fixed key rows with a proportional 72-column grid.
   - Post-fix evidence: `/mnt/NVME_Projetos/MouseKeyboard/design/comparison-keyboard.png` shows all primary controls and a full-width keyboard in the 1480 × 1050 viewport.

## Findings

No actionable P0, P1 or P2 differences remain.

## Follow-up polish

- P3: the source depicts deeper keycap shading; the native implementation intentionally uses flatter GTK buttons to preserve GNOME consistency and interaction states.

final result: passed
