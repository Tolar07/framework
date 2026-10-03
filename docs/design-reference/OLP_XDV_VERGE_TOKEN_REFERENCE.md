# OLP XDV — Verge design tokens (the "Match Intelligence" web pass)

Ratified 2026-08-12 by the Architect (direct instruction + AskUserQuestion).
Source: `docs/design-reference/theverge_DESIGN.md` (awesome-design-md, 73-brand collection).
Applied to `webapp/static/css/proto.css` — the only consumer is `webapp/render_v2.py`.
Replaces the Binance DESIGN.md token pass (ratified 2026-08-10). This is a **skin** —
a ratified design-language change, never a reason to hide data (honest-edge + data
density stay intact; HR35 kept).

## Why The Verge

The mockup is a dark editorial intelligence board (pitch-night canvas, editorial
voice, mono labels, warm amber pick). The Verge's system is the closest match in
the collection: near-black editorial canvas, **mono-uppercase labels**, colour-as-
elevation (1px hairlines instead of shadows), flat surfaces, pill cards, a heavy
display voice. Wired (light canvas, serif) and Kraken (light, purple) were rejected.

## Palette

| Token | Value | Role |
|-------|-------|------|
| `--canvas` | `#131313` | page background |
| `--surface` | `#2d2d2d` | cards |
| `--surface-2` | `#313131` | elevated / active inset |
| `--line` | `rgba(255,255,255,0.14)` | 1px hairlines, tab active inset |
| `--ink` | `#ffffff` | primary text |
| `--ink-dim` | `#949494` | secondary text |
| `--ink-faint` | `#8c8c8c` | captions / hints / honest pending |
| `--amber` | `#e8a33d` | pick/deploy accent — ★ Acca A hero, deploy emphasis, OVERRIDE (mockup's amber kept; Verge tile palette yellow/orange family) |
| `--mint` | `#3cffd0` | hit / positive / trading-up, gate PASS |
| `--ultraviolet` | `#5200ff` | miss / alert / trading-down, data flags |
| `--focus` | `#1eaedb` | `:focus-visible` ring |
| `--link-hover` | `#3860be` | link hover (Verge rule: every link hovers to deep link blue) |

Colour usage is intentionally sparse — a page uses black/white/gray plus at most
one or two accent moments. Don't wallpaper with accent colour.

## Typography

| Role | Family | Substitute for | Use |
|------|--------|----------------|-----|
| display | **Anton** (400) | Manuka | uppercase wordmark, fixture names, section heads |
| ui | **Space Grotesk** (300/500/700) | PolySans | body, controls, tables |
| mono | **Space Mono** (400/700) | PolySans Mono | UPPERCASE labels, timestamps, markets, prices |

Self-hosted under `font-src 'self'` (extend `webapp/static/_fetch_fonts.py`, register
`@font-face` in proto.css). Display sizes keep looser line-height (~+0.10) for the
open-source substitutes, per the DESIGN.md note.

## Rules

- **Mono-uppercase labels** for kickers, timestamps, tab labels, market names.
- **Colour-as-elevation**: 1px hairlines (`--line`) do the work shadows did. No
  decorative gradients, no drop shadows. The Acca A hero accent is a flat
  `--amber` left border + slightly elevated `--surface-2` fill (NOT a gradient).
- Radius: cards ~20px, pills/buttons ~24px, badges ~2px.
- Motion 150–180ms ease; `prefers-reduced-motion` respected; motion is decor,
  never data-hiding.
- **Tier markers dropped**: no Ƈ-A/Ƈ-B chips, no "softness tier A/B" copy — softness
  was fully removed 2026-08-11 (all leagues one open pool, ID405 override). Not restored.
- **Density views are the same public feed**: Lean = the Telegram ticket; Trimmed =
  call cards (MODEL % = `best_model_prob`, DEPLOY = `mes_trigger_price` breakeven,
  all-market bars from `probs`, breakeven strip = `1/price`, booking code); Full = a
  denser grid of the SAME fields. No EV, no source-tier — those stay admin-only
  (trim boundary is protected).

## Boundaries that hold regardless of skin

- The web page IS the Telegram board (one render, two outlets — same feed payload).
- No model internals reach the page: no elo/xg/consensus/EV/verification/`best_price`.
- CSP `script-src 'self'` — no inline handlers; all JS in `proto.js`.
- Gate callout (PASS / OVERRIDE / NOT MET) always visible; `ARCHITECT_SIGNOFF`
  override never silent.
- Honest `NO DATA — PENDING` for any genuinely missing pick/code (HR35).
- Booking codes are SportyBet recall slips, never a stake (Phase-2 bright line).
