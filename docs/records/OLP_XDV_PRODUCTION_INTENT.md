# OLP XDV — PRODUCTION OUTPUT INTENT
### Telegram logic, and how it should shape the web app — for Claude Code

**Reconciliation notice, same as prior reports: you've likely evolved since parts of this conversation happened. Compare against your current implementation before changing anything. Where this document conflicts with something already working better, say so and propose which should win.**

**This document does NOT dictate exact web app layout.** The Architect has an existing web app design (see `OLP_XDV_DESIGN_REPORT.md`, `OLP_XDV_FUNCTION_MAP.md`, and `OLP_XDV_PROTOTYPE.html` from earlier in this process). What follows is the *production logic* — think through how it fits the existing screens rather than treating this as a new spec to bolt on. If something here doesn't translate cleanly to the current UI, propose the adaptation and explain your reasoning rather than forcing a literal 1:1 port from Telegram's text format into web components.

---

## THE CORE PRODUCTION LOGIC

**1. Full scan, every fixture, every market.** For a given day (e.g. 13 fixtures across Champions League qualifiers, Conference League qualifiers, etc.), every fixture gets fully analyzed and every market shown — no silent gaps. Where a fixture genuinely lacks data, it's marked NO DATA — PENDING honestly, not hidden. Report the actual count of fixtures with real data vs. gaps for a given day — some gaps (unrated promoted clubs, uncovered competitions) are structurally expected and won't disappear just from more source ratification; don't imply "zero gaps" is achievable when it isn't.

**2. Acca A — the headline accumulator.** From the full day's scan, select the framework's top 4–5 highest-confidence fixtures.
- **Each leg is that specific fixture's own single highest-probability market — whatever it naturally is.** Do NOT enforce market diversity as a rule. If two fixtures both genuinely have "Over 1.5" as their strongest signal, both legs are Over 1.5 — never downgrade a fixture to a weaker market just to create artificial variety.
- This is confirmed against the Architect's own real result: the ₦578,502 World Cup knockout tickets worked precisely because each leg was that match's true strongest signal, not because of forced diversity.
- Generate one SportyBet booking code for this combined acca.

**3. Remove Acca A's fixtures from the pool.** Once selected, those fixtures are excluded from everything below — no fixture appears in two different bets.

**4. Individual best-pick per remaining fixture.** For every fixture NOT used in Acca A, pull its own single best market (same natural-best logic as above — no forced diversity here either).

**5. Split the remainder into grouped accumulators of ~4-5 legs each.** Never one giant accumulator (too many correlated legs is a structural weakness — the Architect flagged this himself). E.g. 13 total fixtures, 4-5 in Acca A, leaves 8-9 remaining → split into two accas (roughly 4-5 legs each). Each split accumulator gets its own SportyBet booking code.

**6. Every individual single ALSO gets its own booking code** — independent of which accumulator (if any) it's also part of.

**7. Output order:** full board (every fixture, every market, grouped by league) → Acca A (headline) → Acca B/C/D... (split remainder) → individual singles, each with codes.

---

## APPLYING THIS TO THE WEB APP — THINK IT THROUGH, DON'T JUST PORT IT

This logic was designed around Telegram's constraints (linear text, read top-to-bottom). The web app has real UI affordances Telegram doesn't — use them. Some things worth your own judgment on, not mine:

- **Does Acca A deserve a visually distinct "headline" treatment** (like the existing hero-band concept from the prototype) **separate from the split accumulators**, or should all accumulators sit in one consistent list? You have the existing design system — decide what fits it.
- **Where do individual booking codes live** relative to their accumulator groupings — inline per fixture, or a separate "all codes" section? Consider what's actually usable when the Architect is trying to quickly copy-paste into SportyBet.
- **On admin specifically**, given the dense OddsJam-style grid already exists there — does the accumulator grouping need its own dedicated panel, or can it live alongside the existing search/filter view? You know that layout better than this document does.
- **This same logic applies to BOTH the scheduled Telegram delivery AND the web app's Trigger Production button** — one shared backend function should generate the output; only the presentation layer (Telegram text vs. web components) should differ.

Propose your approach before building if you're unsure — this is exactly the kind of judgment call worth a quick confirmation rather than guessing silently.

---

## STILL OPEN FROM EARLIER IN THIS PROCESS (not resolved by this document, just carried forward)

1. **Publish-block clarification** — confirm whether Approve → Publish is blocked by the intentional Phase 3 CLV gate (correct behavior) or an unintended stricter rule blocking on any NO-DATA presence (a bug). Report which, before changing anything.
2. **Europa Conference League** — genuinely new addition, not on the original 15-league whitelist. Needs explicit whitelisting AND a working data source (Football-Data.co.uk likely doesn't cover it, same as Champions League/Europa League/HNL).
3. **Live CLV logging** — the Architect's honest challenge stands: why is the CLV count still 0/30 after this much live production? This is worth chasing as a real bug, separate from the historical backtest.
4. **Historical CLV backtest** — `clv_backtest.py` already exists and is runnable against finished seasons. This should be run now, independent of live-leg accumulation, to give real per-league evidence faster than waiting on live legs one at a time.
5. **"Best price"** — still needs a live odds source (The Odds API / Betfair Exchange) to be a real market price rather than a breakeven trigger price. Don't label a trigger price as a live quote until that source exists.
