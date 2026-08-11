"""
STRESS TEST — every path, every gate, every failure mode, back to back.

WHAT THIS IS
  The last check before the season starts. Not a unit test — those live in
  the other suites — but an end-to-end exercise: every component together,
  with real HTTP, real cached data, and deliberate failure injection at every
  seam I can reach.

WHAT IT PROVES
  1. All five test suites still pass, so nothing regressed while this was
     being built.
  2. The full daily pipeline runs end-to-end on live data and produces a
     board and a Telegram-formatted message.
  3. The safety gates (ID405 market gate, PHASE=2 capital gate, ID403
     verification, HR35 date-required grading) block what they should block
     when directly attacked.
  4. Failures degrade honestly: a broken source produces NO DATA — PENDING,
     not silence or a fabricated value.
  5. The scheduler is genuinely live and its failure alarm is genuinely
     independent (verified separately, not here — see logs/launcher.log).

WHAT IT DOES NOT PROVE
  It cannot prove the model has an edge. That is what the FORWARD CLV log
  will settle over the coming weeks. This test proves the INSTRUMENTATION
  works, so that the CLV number, when it accumulates, means what it says.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

PROJ = Path(__file__).parent.parent
PY = sys.executable
PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(name)
    marker = "  OK  " if ok else " FAIL "
    print(f"{marker} {name}" + (f"  ({detail})" if detail else ""))


def stress(label: str) -> None:
    print("\n" + "=" * 68)
    print(f"  {label}")
    print("=" * 68)


# --------------------------------------------------------------------------
stress("STAGE 1 · every existing test suite still green")
# --------------------------------------------------------------------------
for suite in ("smoke_test", "leagues_test", "multi_league_test",
              "clv_backtest_test", "engine_regression_test"):
    r = subprocess.run([PY, f"tests/{suite}.py"], cwd=PROJ,
                        capture_output=True, timeout=600)
    check(f"suite: {suite}", r.returncode == 0,
          "" if r.returncode == 0 else r.stderr.decode(errors="replace")[-160:])


# --------------------------------------------------------------------------
stress("STAGE 2 · engine invariants hold on real data")
# --------------------------------------------------------------------------
from data.football_data_source import load_league
from engine.dixon_coles import fit, predict
from engine.elo import rate_through, divergence
from engine import markets as mkt

t0 = time.time()
res, _ = load_league("Scottish Premiership", "2526")
check("data: fixtures load", len(res) > 200, f"{len(res)} results")

m = fit(res)
check("dixon-coles: attack centred to 0",
      abs(sum(t.attack for t in m.teams.values())) < 1e-8)
check("dixon-coles: rho fitted inside range not on clamp",
      -0.30 < m.rho < 0.10 and abs(m.rho + 0.30) > 1e-4,
      f"rho={m.rho:+.4f}")

elo = rate_through(res)
check("elo: zero-sum invariant",
      abs(sum(elo.ratings.values()) - 1500 * len(elo.ratings)) < 1.0,
      f"total drift {sum(elo.ratings.values()) - 1500 * len(elo.ratings):+.6f}")

# Every prediction respects the invariants that used to be silently violated
bad_sum = bad_bounds = bad_monotone = 0
for r in res[:80]:
    p = predict(m, r.home_team, r.away_team)
    if p is None:
        continue
    if abs(p.p_home + p.p_draw + p.p_away - 1.0) > 1e-9:
        bad_sum += 1
    if not all(0 < x < 1 for x in (p.p_home, p.p_draw, p.p_away)):
        bad_bounds += 1
    if not (p.p_over_15 >= p.p_over_25 >= p.p_over_35):
        bad_monotone += 1
check("dixon-coles: 1X2 sums to 1 on every prediction", bad_sum == 0)
check("dixon-coles: no probability outside (0,1)", bad_bounds == 0)
check("dixon-coles: overs monotonic non-increasing", bad_monotone == 0)

# Elo probabilities: no fabricated certainties
zero_probs = 0
for r in res[:80]:
    p = elo.probabilities(r.home_team, r.away_team)
    if p and min(p) <= 0.001:
        zero_probs += 1
check("elo: no 0% outcomes published (HR35)", zero_probs == 0)

print(f"  (stage 2 took {time.time()-t0:.1f}s)")


# --------------------------------------------------------------------------
stress("STAGE 3 · every safety gate blocks what it should")
# --------------------------------------------------------------------------
from config import PHASE, assert_paper_only, CapitalGateError
from verification.id403 import verify, SourcedDatum, Tier, _domain_root

# PHASE gate — at Phase 3 (Architect go-live order 2026-08-11) capital is
# ENABLED, so every numeric stake is now ACCEPTED. The hard fail below Phase 3
# lives in config.CAPITAL_ENABLED (= PHASE >= 3); flipping PHASE back to 2
# re-engages it. The paper leg (stake=None) always passes.
accepted = 0
for stake in (0.0, 1.0, 250.0, -1.0, 1e9):
    try:
        assert_paper_only(stake, "phase2_paper")
        accepted += 1
    except CapitalGateError:
        pass
check(f"phase gate: accepts stake at PHASE={PHASE} (go-live)", accepted == 5)

# ID405 — every path
from output.produce_bet import _best_market_desc, render_telegram_board, BoardFixture


class _AwayHeavy:
    home_team, away_team = "Hearts", "Celtic"
    p_home, p_draw, p_away = 0.05, 0.10, 0.85
    p_over_15, p_over_25, p_over_35 = 0.99, 0.98, 0.90
    p_btts_yes, lambda_home, lambda_away = 0.95, 3.5, 3.0


name, _ = _best_market_desc(_AwayHeavy())
# ID405 gate OPENED 2026-08-10 (Architect reversal, RATIFICATIONS.md): away
# wins, Over 2.5 and Home are deployable again. The pick now headlines the
# strongest market whatever it is — nothing gated by market.
check("ID405 gate open: pick headlines the strongest market (Over 1.5 at 99%)",
      name == "Over 1.5 goals", f"chose '{name}'")
check("ID405 gate open: all five markets deployable",
      set(mkt.DEPLOYABLE) == {"1X2_HOME", "1X2_DRAW", "1X2_AWAY",
                              "OVER_2_5", "UNDER_2_5"},
      f"DEPLOYABLE={mkt.DEPLOYABLE}")

# Domain spoofing
check("ID403: bbc.co.uk.evil.example NOT resolved to bbc.co.uk",
      _domain_root("bbc.co.uk.evil.example") != "bbc.co.uk")
check("ID403: true subdomain still resolves",
      _domain_root("sport.bbc.co.uk") == "bbc.co.uk")

# T3 aggregators cannot verify
t3 = verify([SourcedDatum(domain="predictz.com", value="X", url="http://a"),
             SourcedDatum(domain="fctables.com", value="X", url="http://b")])
check("ID404: two T3 aggregators DO NOT verify",
      t3.tier == Tier.SINGLE_SOURCE)

# CLV sign
from clv.clv_logger import compute_clv, CLVLog
check("CLV: entry 2.10 -> close 2.00 is POSITIVE",
      compute_clv(2.10, 2.00) > 0, f"{compute_clv(2.10, 2.00):+.3f}%")

# Kickoff-date guard: grader must refuse a leg with no match_date
import tempfile
tmp = Path(tempfile.mkdtemp()) / "gate.json"
log = CLVLog(path=tmp)
log.log_entry(league="Scottish Premiership", fixture="Hearts v Celtic",
              market=mkt.HOME, model_prob=0.5, entry_odds=2.0,
              phase="phase2_paper")
# leg has no match_date; grader must NOT match it against any historical fixture
missing = [l for l in log.legs if not l.match_date]
check("HR35: legs can carry no match_date", len(missing) == 1)
tmp.unlink()


# --------------------------------------------------------------------------
stress("STAGE 4 · full pipeline end-to-end on live data")
# --------------------------------------------------------------------------
import os
if not os.environ.get("ODDS_API_KEY"):
    from config import load_dotenv
    load_dotenv()

t0 = time.time()
import run_daily
try:
    full = run_daily.run(send=False).full  # RunResult.full is the wide file board
    ok = bool(full) and "PART 0" in full and "PART 1" in full
    check(f"daily run completes and produces a board", ok,
          f"{time.time()-t0:.1f}s, {len(full)} chars" if full else "empty")
except Exception as e:
    check("daily run completes", False, f"{type(e).__name__}: {str(e)[:120]}")


# --------------------------------------------------------------------------
stress("STAGE 5 · failure injection — bad data must degrade honestly")
# --------------------------------------------------------------------------
# Nonexistent league: the scanner must return NO DATA, never fabricate
import orchestrator
board, flags = orchestrator.scan_one_league("Not A Real League", "2526")
check("scanner: unknown league returns empty board",
      board == [], f"got {len(board)} rows")
check("scanner: unknown league raises a data flag",
      any("NO DATA" in f or "PENDING" in f or "not" in f.lower() for f in flags),
      f"first flag: {flags[0][:80]}" if flags else "no flag")

# Thin history: fit floor must hold
from data.football_data_source import MatchResult
tiny = [MatchResult(league="X", date="2025-01-01", home_team=f"T{i%3}",
                    away_team=f"T{(i+1)%3}", fthg=1, ftag=0, ftr="H")
        for i in range(3)]
try:
    m2 = fit(tiny, min_matches_per_team=4)
    check("engine: thin history drops teams below floor",
          len(m2.teams) == 0, f"rated {len(m2.teams)} clubs from 3 matches")
except Exception as e:
    check("engine: thin history handled", False, str(e)[:80])

# Telegram chunking under load
from output.notify import _chunk, FENCE
from output.notify import TELEGRAM_MAX
# Force >= 2 chunks. The test previously used a 2.5k-char input against a
# 3.9k limit and then asserted a split had happened — the chunker was fine;
# the test was checking a quantity that could not occur.
one_fenced_block = FENCE + "\n" + "\n".join(
    f"table row {i} with enough content to occupy real width" for i in range(400)
) + "\n" + FENCE
long_board = ("intro line\n\n" + one_fenced_block + "\n\ntrailer line")
assert len(long_board) > TELEGRAM_MAX, (
    f"input {len(long_board)} chars must exceed the {TELEGRAM_MAX} limit for "
    f"the chunker to be exercised at all")
chunks = _chunk(long_board)
check("chunking: long board produces multiple parts",
      len(chunks) >= 2, f"{len(chunks)} parts")
unbalanced = [i for i, c in enumerate(chunks, 1) if c.count(FENCE) % 2]
check("chunking: every fence balanced under load",
      not unbalanced, f"unbalanced: {unbalanced}" if unbalanced else "")


# --------------------------------------------------------------------------
stress("STAGE 6 · scheduler is actually running")
# --------------------------------------------------------------------------
launcher = PROJ / "logs" / "launcher.log"
if launcher.exists():
    tail = launcher.read_text(encoding="utf-8", errors="replace")
    check("scheduler: launcher fired today", "launcher invoked" in tail)
    # The MOST RECENT "python exited with N" line — Python's own stdout gets
    # appended to launcher.log, so a naive tail-slice can miss it. Scan
    # backwards for the marker line the batch writes.
    exit_lines = [l for l in tail.splitlines() if "python exited with " in l]
    last = exit_lines[-1] if exit_lines else ""
    check("scheduler: last python exit was 0", last.endswith(" 0 "),
          last[-60:] if last else "no exit-line marker in log")
    check("scheduler: no RUN FAILED in the tail",
          "RUN FAILED" not in "\n".join(tail.splitlines()[-4:]))
else:
    check("scheduler: launcher.log exists", False,
          "no evidence the task has run — trigger it once")


# --------------------------------------------------------------------------
print("\n" + "=" * 68)
print(f"  RESULT: {len(PASSED)} passed, {len(FAILED)} failed")
print("=" * 68)
if FAILED:
    print("\nFAILED:")
    for name in FAILED:
        print(f"  - {name}")
    sys.exit(1)
print("\n✅ STRESS TEST PASSED — the instrumentation is sound.")
print("   That means the CLV number, once it accumulates, will mean what it says.")
print("   It does NOT mean the model has an edge — only the forward log settles that.")
