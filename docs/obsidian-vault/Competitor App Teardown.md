# Competitor App Teardown — Odds Scanner AI & ScoreAI

> Reference note, 2026-11-02. Our own analysis of two competitor betting apps,
> captured for if/when we design our own app. **This is design reference, not a
> build spec** (per CLAUDE.md, no new spec docs — amend STATE.md). It records
> the *information architecture* and feature decisions we observed, in our own
> words. It deliberately does **not** reproduce their UI, screenshots, code, or
> assets — copying a competitor's interface is an IP problem; the reusable part
> is the structure and the feature choices, not the pixels.
> Related: [[OLP XDV]], [[Telegram Output Spec]], [[Football-Markets-Catalogue]].

## How this was obtained (and how to refresh it)

Both apps were pulled from the Architect's phone over `adb` and inspected
statically with REA (no servers were probed). The APK binaries were **not**
kept — they are the vendors' copyright and are large. To look again, re-pull:

- Odds Scanner AI: package `com.oddsscanner.ai` (studied at v1.0.5).
- ScoreAI: package `com.scoreai` (studied at v2.8.1).

`adb shell pm path <package>` → `adb pull <base.apk>`. React Native apps hide
their logic in a Hermes bytecode bundle (`assets/index.android.bundle`);
Capacitor apps ship readable JS under `assets/public/`.

---

## Odds Scanner AI — a value-tips product

**Build:** React Native (Expo). Backend is a Payload CMS at
`betting-tips-cms.os-services.xyz`; images at `brain.oddsscanner.ai` /
`media.oddsscanner.ai`. The models run server-side and were not visible.

**Screens / routes:** home · tips · tip detail · history · stats · alerts ·
market picker · strategy picker · profile · subscription · legal. Localised to
3 markets (UK, Chile, Mexico): bookmakers, odds format, currency and copy all
switch on the chosen country.

**What a "tip" carries (the data model worth copying):**
`fairOdds`, `edge`, `confidence` (high/medium/low), `bookmaker` + best odds,
`EV`, `closing`, a `strategy`, `sourceAiModel`/`modelName`, reasoning text, and
— notably — `originalEdge` / `originalFairOdds` / `originalConfidence` kept
separate from any later update. Tips also have expired and "no live offers"
states, a follow/unfollow flag, and won/lost/void alert copy.

**API surface:** `/api/tips`, `/api/tips-archive`, `/api/strategies`,
`/api/strategy-stats`, `/api/strategy-trend`, `/api/tip-follows`,
`/api/user-bets`, `/api/alerts-feed`, `/api/app-strings` (UI copy is
server-driven), auth via email/Google/Apple.

**Feature decisions:**
- Tips grouped into named **strategies**, each with its own public ROI and
  trend chart.
- **Edge** = gap between modelled fair odds and best available price;
  **confidence** = how much data supports it.
- Auto-settling bet tracking (P&L, ROI, hit rate); manual bets too.
- "Free" but with a daily tip limit + subscription; earns from bookmaker
  affiliate sign-ups.

## ScoreAI — an AI chat over Opta data

**Build:** Capacitor (web app in a native shell). Backend `api.scoreai.com`;
Mixpanel analytics; RevenueCat subscriptions; bet365 affiliate links.

**Core idea:** a per-match AI chat. Replies come back typed as text, table,
chart, match list, **bet builder**, **accumulator**, or **value picks**. Their
own terms say the AI relies on third-party model providers — so it is an LLM
reasoning over a stats pack, not a bespoke model.

**Data depth (Opta / Stats Perform):** `matches/{id}/preview|stats/teams|
stats/players|injuries|lineup|squads|commentaries|substitutes|cards`, plus
league tables, team rankings, tournament state.

**Other features:** a `compete` prediction game (leagues, leaderboard,
last-man-standing); a feedback button that rates an answer and attaches a
screenshot; over-the-air code updates (CapacitorUpdater).

---

## What we would take, and what we would NOT

**Take (ideas, re-expressed in our terms):**
1. Keep the published numbers frozen — already done in our CLV ledger
   (`entry_fair_odds`/`entry_edge_pct`, PRs #252/#255).
2. Group picks into named strategies, each with its own ROI/trend record.
3. Fixed-format AI replies (picks / legs / reasoning) rather than free text —
   fits the Gemini verdict panel and the Telegram chat bot.
4. A structured per-tip data model (edge, confidence, best book, closing,
   reasoning, kept-original values).

**Do NOT:**
- Clone their screens, layout, copy, or assets — their IP.
- Build a 40-bookmaker scraper for a "consensus" — the de-margined Betfair
  Exchange already is that (idea 3, PR #255). See
  [[Football-Markets-Catalogue]] and the CLV work.
- Assume their shown ROI/edge is real — it is self-reported, unaudited, and
  their incentive is affiliate clicks, not the user's P&L.

**Honest gaps they have over us:** breadth of odds (40+ books vs our 1–3) and
Opta-grade fixture data. Opta is collected data we cannot self-build; the odds
breadth is largely covered by the exchange consensus.
