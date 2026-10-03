# 002 — Accordion reveal: craft-correct max-height transition

- **Status**: DONE (2026-08-11)
- **Commit**: a3df429
- **Severity**: HIGH
- **Category**: performance / interruptibility
- **Estimated scope**: 1 file (webapp/static/css/proto.css), ~4 lines

## Problem

Both expand/collapse panels animate `max-height`, which is a **layout property** —
the motion standard (AUDIT §5) only allows `transform`/`opacity` on the GPU, and
animating `max-height` forces a reflow every frame of the transition. It is also
**deceptively timed**: the transition runs between `max-height:0` and a large
cap (`600px`/`2400px`), so the visibly-opening part finishes in a fraction of the
250ms while the tail crawls invisibly — the panel feels slower than it looks.

Current code, verbatim:

```css
/* proto.css:84-85 */
.c-league-body{max-height:0;overflow:hidden;transition:max-height 0.25s ease;}
.c-league-body.open{max-height:2400px;}
```

```css
/* proto.css:108-109 */
.c-detail{max-height:0;overflow:hidden;transition:max-height 0.25s ease;}
.c-detail.open{max-height:600px;margin-top:10px;padding-top:10px;border-top:1px dashed var(--line);}
```

## Target

Keep the max-height technique (it is the pragmatic pattern here: no markup change,
no JS measuring) but make it craft-correct — sub-300ms with the strong custom
curve token from plan 001:

```css
/* proto.css — accordion reveal. max-height is a layout animation; the full
   GPU fix (a single-child wrapper + grid-template-rows 0fr→1fr, or JS-measured
   height + transform) is deferred — it needs a markup change in render_v2.py,
   which the other session owns right now. These values keep it responsive and
   honest about its timing; reduced-motion makes it instant (plan 001). */
.c-league-body{max-height:0;overflow:hidden;transition:max-height 200ms var(--ease-out);}
.c-league-body.open{max-height:2400px;}
.c-detail{max-height:0;overflow:hidden;transition:max-height 200ms var(--ease-out);}
.c-detail.open{max-height:600px;margin-top:10px;padding-top:10px;border-top:1px dashed var(--line);}
```

## Repo conventions to follow

- Custom curves come from the `--ease-*` tokens added in plan 001 — never a
  hand-typed cubic-bezier or a built-in keyword.
- The `.open` state must keep its `margin-top`/`padding-top`/`border-top` exactly
  as-is; only the `transition:` value changes.

## Steps

1. `proto.css:84` — change `transition:max-height 0.25s ease;` →
   `transition:max-height 200ms var(--ease-out);` on `.c-league-body`.
2. `proto.css:108` — same change on `.c-detail`.
3. Add the comment block above (documents the deferred GPU fix and why).

## Boundaries

- Do NOT wrap the card children in a new element — that is a markup change in
  `webapp/render_v2.py`, out of scope (other session's in-flight file).
- Do NOT touch `max-height` caps (2400px / 600px) or the `.open` additions.
- Do NOT change `.c-card-top:active`, `.toast`, or chevron transitions (plan 003).
- If the `.open` max-heights differ from what is quoted (drift), STOP and report.

## Verification

- **Mechanical**: same webapp suites as plan 001 (server / render_v2 / export).
- **Feel check**:
  - On `/dashboard`, expand a Call/Scan card and a league group: the reveal
    should feel snappy (fast start, quick settle), not like a slow crawl with a
    long invisible tail.
  - Spam the expand/collapse toggle repeatedly: the transition retargets from
    the current state (CSS transitions) — it must never visibly restart from a
    fully-closed position. (Max-height transitions retarget correctly here;
    confirm it feels continuous.)
  - DevTools → Rendering → emulate `prefers-reduced-motion: reduce`: expand
    collapses instantly (handled by plan 001's `transition:none`).
- **Done when**: both transitions are `200ms var(--ease-out)` and the reveal
  feels crisp in slow-motion (DevTools Animations panel at 10%).
