# 004 — New-row flash: shorten, keep as a comprehension cue

- **Status**: DONE (2026-08-11)
- **Commit**: a3df429
- **Severity**: LOW
- **Category**: accessibility / easing & duration
- **Estimated scope**: 1 file (webapp/static/css/proto.css), ~2 lines

## Problem

When a production run finishes and the admin table reloads, newly-produced rows
flash via a `background-color` keyframe for 1.2s. Against the motion standard
(AUDIT §2, §5): 1.2s is far above the UI budget (a "rare/first-time" moment may
run long, but 1.2s is a long attention-holding blink), and the animation runs
unmodified for reduced-motion users.

The flash is a **good idea** — it tells the Architect which rows are new — so this
plan does not delete it. It tightens the duration and lets plan 001's
reduced-motion block shorten it further (AUDIT §6: keep color/opacity cues that
aid comprehension, drop movement; a background color cue is exactly that).

Current code, verbatim:

```css
/* proto.css:180-181 */
.a-table tr.new-row{animation:flash 1.2s ease;}
@keyframes flash{0%{background:#3a2f1c;}100%{background:transparent;}}
```

## Target

```css
/* proto.css:180 — new-row flash: a short color cue, not a slow blink. */
.a-table tr.new-row{animation:flash 0.9s ease;}
```

The `@keyframes flash` rule stays byte-for-byte identical. Reduced-motion
shortening (to 0.4s) is already handled by plan 001's media block.

## Repo conventions to follow

- It is a one-shot entrance for new data — a color-only (paint) animation on a
  single row class; no `transform`/`opacity` change needed, and no transition
  swap (rows appear after a reload, so nothing can interrupt the keyframe).

## Steps

1. `proto.css:180` — change `animation:flash 1.2s ease;` →
   `animation:flash 0.9s ease;`.
2. Leave `@keyframes flash` untouched.

## Boundaries

- proto.css only.
- Do NOT change the `@keyframes flash` colors or remove the animation.
- Do NOT touch `.a-table tr.new-row`'s `animation-fill-mode` or add delays.
- If the keyframe or class has drifted, STOP and report.

## Verification

- **Mechanical**: webapp suites pass; the admin table still shows the flash.
- **Feel check**: run a board (or reload the admin after one) — the new-row
  highlight should read as a quick "these are new" blink, not a slow fade.
  Emulate `prefers-reduced-motion: reduce`: the flash is shorter (0.4s) but the
  row is still marked.
- **Done when**: the flash is 0.9s normally, 0.4s under reduced motion, and new
  rows remain visually distinct.
