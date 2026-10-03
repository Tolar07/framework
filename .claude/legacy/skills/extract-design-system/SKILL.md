---
name: extract-design-system
description: |
  Reverse-engineer a public website's design primitives (colors, fonts, spacing, radius, shadow) into project-local starter token files. Use when starting a new design system, restyling an interface from a reference site, or extracting tokens to compare against OLP XDV's ratified palette.

  Use when: user wants to reverse-engineer a public website's design tokens into starter files, or audit whether a site's styling matches a reference.
  Don't use when: user asks to change OLP XDV's ratified Binance DESIGN.md tokens in proto.css (that requires Architect ratification, per RATIFICATIONS.md), or asks about prediction internals.
metadata:
  type: reference
  source: external/design-skills/extract-design-system
---

# Extract Design System — design-token extraction tool

**Thin wrapper skill.** The tool lives at
`C:\Users\Motunrayo\omniroute test\external\design-skills\extract-design-system`
(a `SKILL.md` + a Python/npx tool needing Playwright — intentionally NOT copied
into this repo's `.claude/skills/`; the repo stays lean). Read that SKILL.md for
the full workflow; this wrapper points to it.

## Workflow (from upstream SKILL.md)

1. Confirm the target URL is public and reachable.
2. `npx playwright install chromium` then `npx extract-design-system <url>`
3. Review `.extract-design-system/normalized.json` and summarize colors/fonts/spacing.
4. `--extract-only` for artifacts, or `npx extract-design-system init` to
   regenerate starter token files from an existing `normalized.json`.
5. Ask before modifying any existing app code/styles.

## OLP XDV constraint (honest-edge)

Extraction is for *reference and new work*. OLP XDV's palette in `proto.css` is
ratified Binance DESIGN.md tokens — never swap them silently based on an
extraction; that's an Architect ratification decision.
