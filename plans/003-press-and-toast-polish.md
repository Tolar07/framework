# 003 — Press feedback + toast slide polish

- **Status**: TODO
- **Commit**: a3df429
- **Severity**: MEDIUM
- **Category**: physicality / easing & duration
- **Estimated scope**: 1 file (webapp/static/css/proto.css), ~5 lines

## Problem

Two craft gaps against the motion standard (AUDIT §2-3):

1. **Press feedback is imperceptible.** `.c-card-top:active` moves the header
   `translateY(1px)` at a built-in `ease` — 1px on a wide card reads as nothing,
   so the tile never "confirms it heard you". The standard's press pattern is a
   subtle scale (`0.95–0.98`) with a fast `ease-out`.
2. **The toast slides at the top of the UI budget on a weak curve.**
   `transition:transform 0.3s` (built-in `ease`, 300ms) is exactly at the
   300ms ceiling and uses the same weak curve — the toast feels floaty rather
   than crisp.

Current code, verbatim:

```css
/* proto.css:95-96 */
.c-card-top{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;cursor:pointer;border:none;background:none;width:100%;text-align:left;padding:0;color:inherit;transition:transform 0.1s ease;}
.c-card-top:active{transform:translateY(1px);}
```

```css
/* proto.css:100 chevron inside the card top */
.c-card-top .chev{font-size:10px;color:var(--ink-faint);flex:none;align-self:center;transition:transform 0.2s ease,color 0.15s ease;}
```

```css
/* proto.css:82 chevron inside the league head */
.c-league-head .chev{transition:transform 0.2s;color:var(--ink-faint);}
```

```css
/* proto.css:225-227 */
.toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%) translateY(100px);background:#1a1a1a;color:#fff;
  padding:12px 20px;border-radius:8px;font-size:12px;transition:transform 0.3s;z-index:100;max-width:340px;text-align:center;box-shadow:0 6px 24px rgba(0,0,0,.4);}
.toast.show{transform:translateX(-50%) translateY(0);}
```

## Target

```css
/* proto.css:95-96 — press feedback: subtle scale from the top edge. The card
   top is a wide button; scaling toward its own top keeps content anchored. */
.c-card-top{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;cursor:pointer;border:none;background:none;width:100%;text-align:left;padding:0;color:inherit;transition:transform 120ms var(--ease-out);}
.c-card-top:active{transform:scale(0.98);transform-origin:center top;}
```

```css
/* proto.css:100 — chevron rotate uses the strong curve; color stays ease */
.c-card-top .chev{font-size:10px;color:var(--ink-faint);flex:none;align-self:center;transition:transform 200ms var(--ease-out),color 150ms ease;}
```

```css
/* proto.css:82 — league-head chevron: same curve, keep instant default */
.c-league-head .chev{transition:transform 200ms var(--ease-out);color:var(--ink-faint);}
```

```css
/* proto.css:226 — toast slide: under the 300ms ceiling, strong ease-out */
  transition:transform 220ms var(--ease-out);
```

## Repo conventions to follow

- Curves come from the `--ease-*` tokens (plan 001). Hover/color changes keep
  `ease` (AUDIT §2: hover/color → `ease`); movement uses `var(--ease-out)`.
- Press scale stays subtle (0.95–0.98) per AUDIT §3.

## Steps

1. `proto.css:95` — change the `.c-card-top` transition to
   `transform 120ms var(--ease-out)`.
2. `proto.css:96` — change `:active` to `transform:scale(0.98);transform-origin:center top;`.
3. `proto.css:100` — change `.c-card-top .chev` transition to
   `transform 200ms var(--ease-out),color 150ms ease`.
4. `proto.css:82` — change `.c-league-head .chev` transition to
   `transform 200ms var(--ease-out)`.
5. `proto.css:226` — change `.toast` transition to `transform 220ms var(--ease-out)`.
6. Do NOT touch `.toast` position/size/shadow or `.toast.show`.

## Boundaries

- proto.css only — do NOT touch `webapp/static/js/proto.js` (`showToast` is
  class-based and stays untouched; the motion is entirely in CSS).
- Do NOT change `.c-card:hover` border-color transition (`border-color 0.15s ease`
  — a color change, already correct).
- Do NOT change `.c-league-head` background transition (`background 0.1s ease`).
- If any quoted line no longer matches (drift since a3df429), STOP and report.

## Verification

- **Mechanical**: webapp suites (server / render_v2 / export) pass.
- **Feel check**:
  - Tap/hold a Call or Scan card header on `/dashboard`: it should shrink ~2%
    toward the top edge and spring back — a clear "pressed" cue, not a 1px nudge.
  - Trigger a toast (admin → Approve, or copy a booking code): the slide-in
    should feel fast and confident, under 300ms, no floaty tail.
  - Slow-motion (DevTools Animations panel at 10%): press settle is quick and
    smooth; toast starts moving immediately (ease-out), never easing-in.
  - Reduced-motion emulation: press scale is gone (plan 001 sets
    `transform:none`); toast appears instantly.
- **Done when**: press reads as a real press and the toast reads as crisp.
