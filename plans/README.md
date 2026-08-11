# Motion improvement plans — proto.css (improve-animations audit 2026-08-10)

Audit run with the **improve-animations** skill (Emil Kowalski skill pack,
installed at `.claude/skills/`). Scope: the **served** webapp = `proto.css` +
`proto.js` (both `/dashboard` and `/admin` serve only these; `app.css`,
`_fontface.css`, `render.py`, and `design_reference/` are legacy and not served).

`proto.js` was audited and is **clean**: it only manipulates classes/data and
never drives animation — all motion is declarative in `proto.css`. That is the
right shape for a dense, honest-edge dashboard.

## Findings → plans

| # | Title | Severity | Category | Dependencies | Status |
| --- | --- | --- | --- | --- | --- |
| 001 | Easing tokens + reduced-motion foundation | HIGH | tokens / a11y | — | DONE (2026-08-11) |
| 002 | Accordion reveal: craft-correct max-height transition | HIGH | performance | 001 | DONE (2026-08-11) |
| 003 | Press feedback + toast slide polish | MEDIUM | physicality / easing | 001 | DONE (2026-08-11) |
| 004 | New-row flash: shorten, keep as comprehension cue | LOW | a11y / duration | 001 | DONE (2026-08-11) |

## Recommended execution order

1. **001** first — it adds the `--ease-*` tokens every other plan references and
   the reduced-motion block that 002/003/004 depend on.
2. **002** — the highest-visibility motion (accordion reveal feels slow).
3. **003** — press + toast polish (touch-feel cues).
4. **004** — the smallest, last.

Each plan is self-contained for a zero-context executor. Follow each plan's
Boundaries — especially: **proto.css only**, never touch
`webapp/render_v2.py` or `webapp/static/js/proto.js` (the other session owns
those files this week), and STOP + report on drift instead of improvising.

## Judgment calls recorded

- **Max-height accordions stay** (plan 002) rather than moving to a
  GPU-only `grid-template-rows`/transform reveal: the GPU fix needs a
  single-child wrapper — a markup change in `render_v2.py`, currently the other
  session's in-flight file. The plan fixes the craft (curve/duration) and lets
  reduced-motion make it instant.
- **New-row flash is kept** (plan 004): it marks which rows are new — a
  comprehension cue, not decor.
- **Spinner is untouched**: a loading indicator is progress communication.

Co-Authored-By: Claude <noreply@anthropic.com>
