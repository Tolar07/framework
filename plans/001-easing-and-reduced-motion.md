# 001 — Easing tokens + reduced-motion foundation

- **Status**: DONE (2026-08-11)
- **Commit**: a3df429
- **Severity**: HIGH
- **Category**: tokens / accessibility
- **Estimated scope**: 1 file (webapp/static/css/proto.css), ~20 lines

## Problem

proto.css has **no custom easing curves and no `prefers-reduced-motion`
handling at all**. Every transition uses a built-in CSS keyword (`ease`, `ease-out`,
`linear`), which the motion standard (Emil Kowalski skill pack, AUDIT §2) treats as
too weak for deliberate UI motion — built-in `ease` starts and ends slow and makes
interactions feel laggy. And with zero reduced-motion support, every one of the
movements in proto.css (`max-height` accordions, toast slide, chevron rotates, card
press) plays in full for users who request reduced motion — a WCAG requirement
miss.

All other plans (002, 003, 004) depend on the tokens added here.

## Target

Add three motion tokens to `:root`, after the existing radius tokens:

```css
  /* Binance DESIGN.md motion: strong custom curves (Emil Kowalski skill pack,
     improve-animations plan 001). Built-in CSS easings are too weak for UI —
     they start slow, delaying the moment the user is watching most. */
  --ease-out: cubic-bezier(0.23, 1, 0.32, 1);        /* strong ease-out for UI interactions */
  --ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);    /* strong ease-in-out for on-screen movement */
  --ease-drawer: cubic-bezier(0.32, 0.72, 0, 1);     /* iOS-like drawer curve (reserved) */
```

Add one reduced-motion block at the end of the file (after the responsive
media queries):

```css
/* Reduced motion (improve-animations plan 001): movement drops to instant;
   color/opacity feedback (hovers, active backgrounds) is kept — it aids
   comprehension. The spinner stays: a loading cue is progress, not decor. */
@media (prefers-reduced-motion: reduce){
  .c-detail, .c-league-body { transition: none; }
  .c-card-top:active { transform: none; }
  .c-card-top .chev, .c-league-head .chev { transition: none; }
  .toast { transition: none; }
  .a-table tr.new-row { animation-duration: 0.4s; }
}
```

## Repo conventions to follow

- Tokens live in the `:root` block of `webapp/static/css/proto.css` (already has
  `--r-xs`…`--r-pill` added 2026-08-10); add the motion tokens in the same block.
- `prefers-reduced-motion` blocks are placed after the last `@media` in the file
  (mirror the existing `@media (min-width:760px)` / `@media (max-width:480px)` style).

## Steps

1. In `webapp/static/css/proto.css`, inside `:root` after the `--r-*` radius
   tokens, add the three `--ease-*` tokens (exact code above).
2. Append the `@media (prefers-reduced-motion: reduce)` block to the end of the
   file (exact code above).
3. Do NOT yet change any existing `transition:` values — that is plans 002/003.

## Boundaries

- Do NOT touch `webapp/render_v2.py`, `webapp/static/js/proto.js`, or any
  non-CSS file — proto.css only.
- Do NOT change markup/structure.
- Do NOT change the spinner (`@keyframes spin`) or its `animation` rule.
- Do NOT add dependencies or JS.
- If `proto.css` no longer matches the code quoted above (drift since a3df429),
  STOP and report instead of improvising.

## Verification

- **Mechanical**: `python -m pytest tests/webapp_server_test.py` — the
  `/static/css/proto.css` assertions (`"font-family" in body`) must still pass;
  run `tests/webapp_render_v2_test.py` and `tests/webapp_export_test.py` too.
- **Feel check**:
  - Load `/dashboard` and `/admin/2026-08-10`. Confirm no rule is broken by the
    `:root` additions (open DevTools → Elements → computed `--ease-out` =
    `cubic-bezier(0.23, 1, 0.32, 1)`).
  - DevTools → Rendering → Emulate `prefers-reduced-motion: reduce`. Expand a
    card and a league group: the detail/body must appear **instantly** (no height
    crawl), and the chevron must snap (not rotate). Hover a card: border-color
    still transitions (color kept). Click the Publish/Approve button: still
    pressable, no motion.
- **Done when**: the three tokens exist in `:root`; the reduced-motion block is
  present; reduced-motion emulation shows instant accordion/toast/chevron with
  color feedback intact.
