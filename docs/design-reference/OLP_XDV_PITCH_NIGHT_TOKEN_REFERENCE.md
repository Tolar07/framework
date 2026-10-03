# OLP·XDV — Pitch-Night Editorial Token Reference

Ratified **2026-08-12** by the ARCHITECT ("use this code for the webapp").
**Supersedes** the Verge token pass (ratified 2026-08-12 earlier the same day; itself
the replacement for the 2026-08-10 Binance pass). See `RATIFICATIONS.md`.

Source document (kept verbatim for fidelity):
`docs/design-reference/pitch_night_mockup.html` — the "OLP·XDV — Match Intelligence"
pitch-night editorial board mockup.

## Design language

A phone-first dark editorial football-intelligence board: deep-green near-black canvas,
chalk ink, one warm amber accent for the pick/deploy line, colour-as-elevation (no
shadows or gradients — only hairlines and layered surfaces), a heavy condensed serif
display voice, mono-uppercase micro-labels, animated SVG dials + all-market bars +
breakeven edge strips, and a density switcher (Lean / Trimmed / Full) that renders the
SAME public feed fields at three densities.

## Core tokens

| Token            | Value      | Role                                        |
|------------------|------------|---------------------------------------------|
| `--pitch-night`  | `#0e1a16`  | canvas (page background)                    |
| `--pitch-elevated`| `#142720` | surface (cards, ticket, scan header)        |
| `--pitch-line`   | `#26392f`  | hairline / track / border                   |
| `--chalk`        | `#f2efe4`  | ink (primary text)                          |
| `--sage`         | `#93ab9c`  | ink-dim (secondary text)                    |
| `--sage-dim`     | `#5c7268`  | ink-faint (captions, disabled)              |
| `--amber`        | `#e8a33d`  | pick / deploy / positive accent             |
| `--clay`         | `#c05a4c`  | pending / missing / alert                   |

Semantics on the public board:
- **amber** = the deployed pick, the MODEL dial, DEPLOY breakeven line, booking code,
  favorite bar, `.yes` scan cell, `.pill.on` active tab. Positive action.
- **clay** = anything honestly missing (`NO DATA — PENDING`), italic + clay.
- **sage / sage-dim** = secondary copy, hairline captions, `.no` scan cell.

## Type scale (self-hosted under `font-src 'self'`)

| Role              | Family          | Weights                     |
|-------------------|-----------------|-----------------------------|
| Display           | `Fraunces`      | 400, 500, 600, 700 (opsz 9..144) |
| Body / UI         | `Inter`         | 400, 500, 600, 700          |
| Mono / micro-label| `IBM Plex Mono` | 400, 500, 600               |

- Display voices: `.wordmark`, `.section-title`, `.call-fixture`, `.single-fixture`,
  `.ticket-title`, `.combined-price`.
- Mono-uppercase micro-labels: `.section-eyebrow`, `.call-league`, `.call-market`,
  `.mkt-fam-label`, `.mkt-block-label`, `.code-label`, `.densitybar-label`,
  `.ticket-legs-count`, `.combined-label`, `.code-label-t`, `.ticket-singles-label`,
  `.single-league`, scan table `thead`, `.foot-bottom`.
- Numerals use `font-variant-numeric: tabular-nums` on `.count`.

## Structure of the board

1. **Masthead** — `.wordmark` ("OLP·XDV", amber middle dot), `.centerline` hairline
   with a sage node, live phase pill (Phase 3 = live capital, Architect-deployed).
2. **Tab nav** — sticky `.tabnav` with `.pill` buttons **CALL / SCAN / SINGLES**,
   amber `.on` active state, scrollspy + smooth scroll.
3. **Hero** — honest-edge line ("An excellent informed process. Not, on its own, a
   demonstrated profitable edge…"), CTA buttons, one-shot sweep highlight; **gate
   callout strip is always visible** (PASS=mint→sage / OVERRIDE=amber / NOT MET=muted —
   override never silent). Gate is a public feed field.
4. **Part 1 · THE CALL** — density switcher (`Lean` / `Trimmed` / `Full`):
   - **Lean** = byte-faithful Telegram ticket: `★ Acca A — HEADLINE`, legs
     `fixture (league) — market @ price`, `Combined X.XX`, booking code; then singles,
     one slip each, own code, honest `NO DATA — PENDING` when null.
   - **Trimmed / Full** = `.call-card` grid: league kicker, `.call-fixture`,
     `.call-market`, SVG `.dial` (MODEL %, amber fill), DEPLOY breakeven line,
     all-market bars (1X2 / O1.5 / O2.5 / BTTS / DC from public `probs`, favorite =
     `.fav`), breakeven edge strip (model vs breakeven, "not a live quote"), booking-code
     pill (`.code-row`, `.pending` when missing).
   - **Full** renders the SAME public feed fields as a denser grid. **No EV, no source
     tier, no model internals on the public board** (Architect trim boundary; "Full
     requires Architect sign-in" logic from earlier mockups stays OUT — Full is
     feed-data-only).
5. **Part 2 · THE SCAN** — `.scan-table-wrap` > `table.scan`: fixture (+league) |
   1X2 | O1.5/O2.5 | BTTS | live. Honest `.pending` rows. Each row keeps `.f-scan-row`
   (live-score polling target). `thead` sticky under the tabnav.
6. **Part 3 · SINGLES** — density switcher; lean `.single-line` rows w/ codes;
   trimmed/full `.single-card` grid w/ small dials.
7. **Yesterday — GRADED** and **7-day rolling** — Telegram-carrying sections, kept and
   re-skinned (PROMPT3: everything Telegram carries is on the page).
8. **Footer** — honest-edge note + "All capital deployment decisions rest solely with
   the Architect." + `Capital authority: THE ARCHITECT`. Phase line is current
   (**Phase 3 is LIVE**, not "opens only once thirty logged paper legs…").

## Interaction / motion

- **Dials** — `setupDials()` computes circumference `2πr` from `data-radius`, sets
  `stroke-dasharray`/`stroke-dashoffset`; `fillDials(scope)` animates to the target.
- **Bars** — `fillBars(scope)` sets `width` from `data-value`.
- **Reveal** — IntersectionObserver on `.reveal` (threshold 0.15) adds `.show` and
  fills dials/bars once; unobserve after.
- **Density** — click `.density-pill` → toggle `.on`, cross-fade `.density-view`
  (`.active` + `.in` via double rAF), fill the newly-active view.
- **Scroll nav** — every control is a real `<button>` wired via `addEventListener`
  (`[data-scroll-target]` → `scrollIntoView`), CSP-clean (zero inline handlers).
- **Reduced motion** — `@media (prefers-reduced-motion: reduce)` kills animation and
  fills dials/bars instantly; no-JS fallback fills the default-active view.

## Honest-edge / boundary (unchanged)

Tokens are a **skin** — never a reason to hide data. Data-density constraints intact:
public fields are fixture, league, `best_market`, `best_model_prob` (MODEL %),
`mes_trigger_price` (DEPLOY breakeven — not a live quote), `probs`
(p_home/p_draw/p_away, p_over_15/25, p_btts_yes + derived DC), `on_deploy_shortlist`,
`kickoff_date`, `rejection_reason`, `gate_state`. NEVER `best_price`, `best_mes_ev`,
verification, elo/xg/consensus, EV, or source-tier. HR35 kept: every genuinely-missing
number reads `NO DATA — PENDING` until it is real. No capital on the board — read-only
intelligence.
