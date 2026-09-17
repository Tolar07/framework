# OLP XDV — FINAL TELEGRAM OUTPUT SPEC

**Status: RATIFIED — supersedes all prior Telegram render formats**
**Date: 2026-09-17 · Architect-approved**

> Pasted verbatim by the Architect on 2026-09-17 and stored here as canonical.
> Supersedes `TELEGRAM_BLEND_DESIGN.md` (26–27 Aug) in full.
> Implementation status is tracked at the bottom of this note — the spec text
> itself is the Architect's and is not edited by Claude Code.
> Related: [[Rules.md]], [[STATE.md]], [[Decisions Log.md]], [[Protected Constants.md]]

---

## 0. DIRECTIVE — FORMAT CONSOLIDATION

This document defines the **single** Telegram output format for OLP XDV.

**SUSPENDED as of this document — do not call, do not maintain:**
- `render_heartbeat_compact()` in its current form — the `[HEARTBEAT]`
  header is removed; the stacked per-fixture layout is retained and
  becomes the basis of the production board below
- `render_layer2_full_grid()` — the four-table `compact=False` blend
- `render_layer1_compact()`
- `render_the_pick()`
- `TELEGRAM_BLEND_DESIGN.md` (26–27 Aug) — superseded in full
- Any monospace fixed-width table format for Telegram delivery

**ACTIVE — the only Telegram render path:**
- `render_production_board()` — Sections 1–3 below
- `render_acca_route()` — Section 4 below (retained, reworked)

Rationale: the four-table blend renders clumsy on a phone. The stacked
per-fixture block is readable at phone width without horizontal scroll
and satisfies HR53 (full detail, plain language, nothing cramped).

---

## 1. HEADER

No `[HEARTBEAT]` tag. No DATA FLAGS summary block — per-fixture `Src`
stamps carry that information already and the header count duplicated it.

```
##########OLP XDV#########
==================================
FULL PIPELINE BOARD — PRODUCTION
Thu 17 Sep 2026 · all markets · AI pick
Run ID: OLPXDV-20260917-0700-a4f91c | Phase 3 — LIVE
Fixtures scanned: 22 · Verified: 20
```

`Run ID` is **mandatory** and must trace to literal fetch-script stdout
(HR59). A board without a valid `run_id` must be rejected by the send
gate before it reaches Telegram. This is a code-level gate, not a
review step.

---

## 2. PER-FIXTURE BLOCK

Grouped by competition. Competition header carries country flag + name.
Within a competition, sort by AI pick confidence, highest first.

```
──────────────────────────────────
🏆 CHAMPIONS LEAGUE
──────────────────────────────────
20:00  Lyon v Fenerbahçe
1X2   Lyon 52% · Draw 26% · Fenerbahçe 22%
DC    Lyon or Draw 78% · Lyon or Fener 74% · Draw or Fener 48%
O/U   O1.5 81% · O2.5 58% · O3.5 36%
      U1.5 19% · U2.5 42% · U3.5 64%
BTTS  Yes 58% · No 42%
🤖 AI PICK: Over 1.5 goals — 81%
      EV +5.4% (model 81% vs market 75.6%) · Deploy at 1.24+
      Src ✓ VERIFIED · Booking code: PENDING
```

### Field rules

| Field | Rule |
|---|---|
| Kickoff | Real confirmed time only. Never `??:??` — a fixture without a second-source confirmed kickoff is held off the board (pre-grade liveness standard). |
| 1X2 | All three outcomes always, named by club not glyph (HR53). |
| DC | All three combinations always. Never only the favourite's DC — that hides the away-side option. |
| O/U | **Both sides printed on separate lines.** Fixes BUG5 permanently: a 46% Over must never render as "O46" when the honest label is "U54". |
| BTTS | Yes and No both printed. |
| AI PICK | Single strongest market by EV for that fixture — not defaulted to 1X2. Plain language, full club name, market named in words. |
| EV | `(model_prob − market_implied_prob) × 100`. Shown with both inputs visible so the number is auditable, never bare. |
| Deploy at | MES trigger price. Architect-fed odds; framework outputs the trigger, Architect enters the real SportyBet/Bet365 price. |
| Src | ID403/ID404 stamp: `✓ VERIFIED` / `○ SINGLE-SOURCE` / `⚠ CONFLICT` |
| Booking code | `PENDING` pipeline-wide until `read_betslip_combined_odds` is fixed (currently returns `100.0` instead of real combined odds). |

### Sub-threshold picks

A fixture whose best market falls below the EV threshold still renders
in full, tagged so it cannot be mistaken for a recommendation:

```
🤖 AI PICK: Under 2.5 goals — 54%
      EV +1.2% (model 54% vs market 52.8%) · below +2.0% threshold
      → SCAN ONLY, not deploy-eligible
      Src ✓ VERIFIED · Booking code: PENDING
```

---

## 3. NO-DATA HANDLING

**Architect directive (17 Sep):** NO-DATA fixtures are removed from the
main board. They no longer occupy a per-fixture block.

**Implementation — collapsed footer line, one line total:**

```
──────────────────────────────────
2 fixtures unresolved — no market data after 2 retries:
Everton v Wolves · Rayo v Osasuna    (full detail: run log a4f91c)
```

### Why this line exists and must not be deleted

HR58 zero-silent-drops. HR35 absolute. A fixture the pipeline failed to
fetch is not a fixture that doesn't exist. Deleting the line does not
create data — it hides that data is missing, and a board that looks
complete while silently dropping fixtures is the precise condition that
produced the 3 Sep fabrication incidents (fabricated fixture list with
false FlashScore/SofaScore attribution).

**The correct remedy is upstream, not in the renderer:** HR58 already
mandates multi-source redundancy, retry logic, and paid API keys as
primary in the fetch layer. Reducing this line to zero fixtures is an
engineering target for the fetch layer. It is not achieved by deleting
the line.

If this line is ever renders empty, print nothing — no "0 unresolved"
line. Clean board, earned.

---

## 4. ACCA ROUTE

Appended after the last competition block. Rendered only when the
eligible pool supports at least one full acca.

### 4.1 Eligibility — a pick enters the acca pool only if ALL hold

1. `Src = ✓ VERIFIED` (ID403 two-factor minimum). SINGLE-SOURCE and
   CONFLICT never enter an acca.
2. `EV ≥ +2.0%`
3. `deploy_price ≤ 1.50` — ID420 odds ceiling, lowered from 2.00 on
   2 Sep. Applies per leg, regardless of edge.
4. Market not on the banned list (Correct Score, Bookings, First Half
   U0.5, NBA spread ≤2.5 moneylines, NBA Over bracket capital).
5. One leg per fixture — never two markets from the same match.

### 4.2 Formation

```python
LEGS_PER_ACCA = 5          # Architect-specified
MAX_ACCAS     = 2          # standing rule: 2 accas + 1 SLV per session
MIN_SHORT_ACCA = 3         # remainder threshold
```

- Rank eligible pool by EV descending.
- Chunk sequentially into accas of `LEGS_PER_ACCA`.
- Cap at `MAX_ACCAS`. Surplus eligible picks beyond the cap render in a
  SURPLUS list as singles — visible, never discarded.
- Remainder of 3–4 legs → one SHORT ACCA, labelled as such.
- Remainder of 1–2 legs → SLV singles.
- Combined odds ceiling per acca: none specified. Five legs at the 1.50
  per-leg ceiling caps combined at ~7.59 naturally.

### 4.3 ⚠ UNRESOLVED DIRECTIVE CONFLICT — Architect decision required

The Architect described (17 Sep): *16 picks → accas of 5 legs; 20+ picks
→ more accas.* At 5 legs that implies **3–4 accas per session**.

The standing rule is **2 accas + 1 SLV per session**, explicitly
reaffirmed 14–15 Aug when the Architect rejected raising it to 4–5 accas
covering the full daily slate.

`MAX_ACCAS` is left at **2** pending explicit Architect ratification.
It is a config constant — changing it to 4 requires no code change.
This conflict is surfaced, not silently resolved (HR56: directives are
binding law, no silent reversion).

### 4.4 Render format

```
──────────────────────────────────
🎟️ ACCA ROUTE
──────────────────────────────────
Eligible pool: 13 of 22 scanned
Formed: 2 accas × 5 legs · Surplus: 3 picks → singles
(MAX_ACCAS = 2 — standing rule, see §4.3)

▸ ACCA A — 5 legs · EV rank 1–5
1. Lyon v Fenerbahçe — Over 1.5 goals .......... 81% @ 1.24
2. Celje v Slovan — Both teams to score, yes ... 72% @ 1.39
3. Arsenal v Brentford — Arsenal or Draw ....... 89% @ 1.12
4. Ajax v Willem II — Ajax to win .............. 78% @ 1.28
5. Midtjylland v Lyngby — Over 2.5 goals ....... 64% @ 1.58
   ──────────────────────────────────
   Combined odds ............... 4.01
   Combined model probability ... 25.9%
   Break-even probability ....... 24.9%
   Model edge ................... +1.0pp
   Booking code: PENDING

▸ ACCA B — 5 legs · EV rank 6–10
   [same structure]
   Combined odds ............... 5.12
   Combined model probability ... 19.4%
   Break-even probability ....... 19.5%
   Model edge ................... −0.1pp  ⚠ NEGATIVE
   Booking code: PENDING

▸ SURPLUS — 3 eligible picks, beyond acca cap, as singles
   Twente v ADO Den Haag — Twente to win .. 61% @ 1.64  ⚠ above 1.50 ceiling
   [...]
   Booking codes: PENDING

HONEST EDGE: combined probability is the product of legs, not an
average. Five legs at ~75% each land 23.7% of the time. Accumulator
returns are not edge evidence — per the Accumulator Honesty Rule, acca
outcomes remain quarantined from the calibration log.
```

### 4.5 Mandatory acca disclosures

Every acca prints **combined model probability and break-even side by
side**, always. Reason: a five-leg acca of strong-looking legs reads as
high confidence and is not. Combined probability is the product of the
legs. Any acca where `model_prob < break_even` renders with a
`⚠ NEGATIVE` flag and must not be presented as the recommendation.

Acca results stay quarantined from calibration (Accumulator Honesty
Rule). The 31-leg / 30W World Cup acca run remains logged as a pilot,
not edge evidence.

---

## 5. MESSAGE CHUNKING — OPEN ENGINEERING ITEM

Telegram caps a message at 4096 characters. This format runs ~7 lines
per fixture (~340 chars). Practical ceiling: **11–12 fixtures per
message**.

With the whitelist expanding toward ~61 competitions, a 60-fixture slate
is ~5–6 chunked messages per morning push. Naive mid-block chunking will
split fixtures across message boundaries.

**Required:** chunk on **competition boundaries**, never mid-fixture.
One message per competition where a competition fits; split large
competitions on fixture boundaries with a `(cont.)` header.

Header renders once, on message 1. Acca Route renders once, as the
final message. Honest-edge footer renders once, on the final message.

**Unresolved:** whether the full 7-line block is retained for all
fixtures at 60-fixture scale, or restricted to deploy-eligible fixtures
with a compressed one-line format for the remainder. Architect decision.

---

## 6. IMPLEMENTATION NOTES

- One shared `board_data` object feeds the renderer. No surface
  recalculates — same fixtures, same model output, same EV numbers.
- `render_production_board(board_data) -> list[str]` returns
  competition-chunked message strings, not one blob.
- Send gate rejects any message list lacking a valid `run_id` (HR59).
- No stake amounts, no "place now" language anywhere. A booking code is
  a lookup reference. Capital deployment is Architect-only, always.
- Phase label reads from the static deployment flag, **not**
  re-derived from live calibration counts — this was the 28 Aug bug
  where the board printed "Phase 2 — PAPER ONLY" after the Architect
  had moved to Phase 3, because the generator re-derived phase from a
  0/30 calibration state.
- CLV logging currently suspended (22 Aug). The CLV fields remain in the
  data structure; they are not rendered while suspended.

---

## 7. HONEST EDGE FOOTER — MANDATORY, EVERY BOARD

```
==================================
HONEST EDGE: an excellent informed process, NOT a demonstrated
profitable edge. Capital authority: THE ARCHITECT.
```

Non-removable. Renders on the final message of every chunked board.

---

## IMPLEMENTATION STATUS — maintained by Claude Code, not part of the spec

As of 2026-09-17, this spec is **ratified but NOT yet implemented**.
`render_production_board()` does not exist. The live Telegram path is still
`render_stage_b_output()` + `render_telegram_blend()`.

Confirmed already satisfied:
- §6 phase label — `_phase_banner()` in `output/produce_bet.py` derives from
  `config.PHASE` (currently 3), not from calibration counts. The 28 Aug
  "Phase 2 — PAPER ONLY" regression is closed.
- §2 O/U both sides — `p_over_35` is mapped in `engine/markets.py` and
  `UNDER_35` is derived; the renderer has both sides available.
- §4.1(3) 1.50 ceiling — `MAX_ODDS_CAP` is config-driven, set to 1.50.

Open work to reach full compliance:
1. `render_production_board()` — stacked per-fixture block, competition
   grouping, competition-boundary chunking (§1–3, §5).
2. Send-gate `run_id` rejection (§1) — currently no code-level gate.
3. NO-DATA collapsed footer line (§3) — fixtures currently render as rows.
4. Retire the suspended renderers listed in §0.
5. §4.3 `MAX_ACCAS` conflict — left at 2, awaiting Architect ratification.
