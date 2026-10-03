---
name: ui-ux-pro-max
description: |
  UI/UX design intelligence toolkit — searchable databases of 84 UI styles, 192 color palettes, 74 font pairings, 98 UX guidelines, and 25 chart types across 22 tech stacks. Use when designing/restyling a dashboard, choosing color/font/chart, or auditing UX best practices.

  Use when: user asks about UI style selection, color palette choice, font pairing, chart type selection, or UX guideline compliance for the OLP XDV webapp or any interface work.
  Don't use when: user asks for OLP XDV data/prediction internals (use olp-xdv), or wants the ratified Binance DESIGN.md tokens swapped (tokens are ratified — any design-language change needs an Architect ratification first).
metadata:
  type: reference
  source: external/design-skills/ui-ux-pro-max-skill
---

# UI/UX Pro Max — design intelligence toolkit

**Thin wrapper skill.** The full toolkit lives at
`C:\Users\Motunrayo\omniroute test\external\design-skills\ui-ux-pro-max-skill`
(24 MB — intentionally NOT copied into this repo's `.claude/skills/`; the repo
stays lean). It has no top-level `SKILL.md`; it is a CLI toolkit.

## Use

Search its databases via the CLI (Python 3):
```bash
cd "/c/Users/Motunrayo/omniroute test/external/design-skills/ui-ux-pro-max-skill"
python3 src/ui-ux-pro-max/scripts/search.py --help   # discover the query flags
```

Or read the skill's own `CLAUDE.md` / `docs/` for the capability list and
query patterns before using it.

## OLP XDV constraint (honest-edge)

UI styling in this repo is governed by the **ratified Binance DESIGN.md tokens**
(`webapp/static/css/proto.css`). This toolkit is a *reference* for new UI work,
never a reason to silently swap the ratified palette — a design-language change
must be ratified by the Architect first (see `RATIFICATIONS.md`). Tokens are a
skin, never a reason to hide data.
