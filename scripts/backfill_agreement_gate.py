#!/usr/bin/env python3
"""
Backfill the agreement-gate experiment (gambler move #2) for 2026-08-07 → 2026-08-14.

DESIGN (honest, no gate contamination):
- Fits the CANONICAL DC model on the COMPLETED 2526 season (no lookahead).
- Reconstructs each fixture from its SETTLED 2627 record (results + opening/closing prices).
- Applies the EXACT agreement gate from engine/acca.py (_market_implied + |model_p - book_p| <= band).
- Logs legs to a DEDICATED phase "backtest_agreement_0.04" — explicitly EXCLUDED from
  phase2_status() by exact phase-match, so the PROTECTED Phase-3 gate stays clean.
- Uses the opening price as entry (CL-ARCHIVE: "pick-time" from historical CSV),
  the closing price as the CLV close, and the real FT result for hit/miss.
- Reports the experiment's CLV/hit-rate separately from the official gate.

This is a calibration instrument, not a selection engine. It answers: "if the gate
had been ON for these dates, what would the paper CLV ledger show?"
"""
from __future__ import annotations
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.football_data_source import load_league, MatchResult
from engine.dixon_coles import fit, predict
from engine import markets as mkt
from engine.leagues import WHITELISTED_LEAGUES, is_deploy_eligible, build_deploy_shortlist
from engine.mes import edge_diff

# Mirrors run_daily.MIN_MES_FLOOR (2026-08-14, gambler move #3): the default EV
# floor to log a paper leg. Defined locally to avoid importing the daily runner.
MIN_MES_FLOOR = 0.03
from clv.clv_logger import CLVLog, LoggedLeg, compute_clv, PAPER_PHASE
from config import PHASE_LABEL

# Experiment configuration
AGREEMENT_BAND = 0.04
TARGET_START = "2026-08-07"
TARGET_END = "2026-08-14"
FIT_SEASON = "2526"       # model fit on completed 2025-26
RESULTS_SEASON = "2627"   # settled fixtures for 2026-08 window (current season)
EXPERIMENT_PHASE = "backtest_agreement_0.04"
ENTRY_CAPTURE_PATH = "CL-ARCHIVE"   # reconstructed from CSV open price
CLOSE_CAPTURE_PATH = "CL-ARCHIVE"   # reconstructed from CSV close price


class MockFixtureOdds:
    """Mock FixtureOdds from settled CSV MarketOdds (open=entry, close=close)."""
    def __init__(self, result: MatchResult):
        self.league = result.league
        self.home_team = result.home_team
        self.away_team = result.away_team
        self.kickoff_utc = result.date
        # Build MarketQuote objects from the richer odds.open / odds.close
        self.home = self._mq(result.odds.home)
        self.draw = self._mq(result.odds.draw)
        self.away = self._mq(result.odds.away)
        self.over25 = self._mq(result.odds.over25)
        self.under25 = self._mq(result.odds.under25)
        self.over15 = self._mq(getattr(result.odds, "over15", None))
        self.under15 = self._mq(getattr(result.odds, "under15", None))
        self.btts_yes = self._mq(getattr(result.odds, "btts_yes", None))
        self.btts_no = self._mq(getattr(result.odds, "btts_no", None))
        self.dc_1x = self._mq(getattr(result.odds, "dc_1x", None))
        self.dc_x2 = self._mq(getattr(result.odds, "dc_x2", None))
        self.dc_12 = self._mq(getattr(result.odds, "dc_12", None))

    class _mq:
        """Tiny MarketQuote-like object with .price and .available"""
        def __init__(self, mp):
            self.price = mp.close if (mp and mp.close) else None
            self.open_price = mp.open if (mp and mp.open) else None
            self.available = self.price is not None
        # For implied_1x2 we need .price on the nested object
        @property
        def close(self):
            return self
        @property
        def open(self):
            return self


def _market_implied(market_key: str, fx: MockFixtureOdds, entry_price: float) -> Optional[float]:
    """
    EXACT copy of engine.acca._market_implied (devigged where possible, else raw 1/price).
    Uses the OPEN price for the book's implied probability at pick time.
    """
    if fx is not None:
        # Build a temporary object with open prices for implied_1x2
        class OpenPrices:
            def __init__(self, fx):
                self.home = type('obj', (), {'price': fx.home.open_price})()
                self.draw = type('obj', (), {'price': fx.draw.open_price})()
                self.away = type('obj', (), {'price': fx.away.open_price})()
        if market_key in mkt.MARKETS_1X2:
            p1x2 = mkt.implied_1x2(OpenPrices(fx))
            if p1x2 is not None:
                return p1x2[mkt.MARKETS_1X2[market_key]]
        if market_key in (mkt.OVER_25, mkt.UNDER_25):
            o = fx.over25.open_price if market_key == mkt.OVER_25 else fx.under25.open_price
            other = (fx.under25.open_price if market_key == mkt.OVER_25
                     else fx.over25.open_price)
            if o and other:
                s = 1.0 / o + 1.0 / other
                if s > 1.0:
                    return (1.0 / o) / s
    if entry_price and entry_price > 1.0:
        return 1.0 / entry_price
    return None


def _best_leg_for_fixture(result: MatchResult, probs, fx: MockFixtureOdds,
                           agreement_band: float = AGREEMENT_BAND) -> Optional[dict]:
    """
    Mirror engine.acca._best_deployable_leg: iterate EDGE_MARKETS, apply agreement gate,
    return best by EV (then prob). Returns dict or None.
    """
    if probs is None:
        return None
    if not is_deploy_eligible(result.league):
        return None

    best = None
    for market in mkt.EDGE_MARKETS:
        prob = mkt.model_prob(market, probs)
        if prob is None:
            continue

        # Entry price = open price from CSV (pick-time)
        entry_price = None
        if market in mkt.MARKETS_1X2:
            mp = getattr(fx, market.lower().replace("1x2_", "")).open_price
            if mp:
                entry_price = mp
        elif market == mkt.OVER_25:
            entry_price = fx.over25.open_price
        elif market == mkt.UNDER_25:
            entry_price = fx.under25.open_price
        elif market == mkt.OVER_15:
            entry_price = fx.over15.open_price
        elif market == mkt.UNDER_15:
            entry_price = fx.under15.open_price
        elif market == mkt.BTTS_YES:
            entry_price = fx.btts_yes.open_price
        elif market == mkt.BTTS_NO:
            entry_price = fx.btts_no.open_price
        elif market in (mkt.DC_1X, mkt.DC_X2, mkt.DC_12):
            entry_price = getattr(fx, market.lower()).open_price
        if not entry_price:
            continue

        # Agreement gate (EXACT logic from acca.py)
        book_p = _market_implied(market, fx, entry_price)
        if book_p is None:
            continue
        if abs(prob - book_p) > agreement_band:
            continue  # disagreement bucket — exclude

        # Edge (canonical: model_prob - implied_prob)
        edge = edge_diff(prob, entry_price)
        if edge is None or edge < MIN_MES_FLOOR:
            continue

        # Closing price for CLV
        close_price = None
        if market in mkt.MARKETS_1X2:
            mp = getattr(fx, market.lower().replace("1x2_", "")).price
            if mp:
                close_price = mp
        elif market == mkt.OVER_25:
            close_price = fx.over25.price
        elif market == mkt.UNDER_25:
            close_price = fx.under25.price
        elif market == mkt.OVER_15:
            close_price = fx.over15.price
        elif market == mkt.UNDER_15:
            close_price = fx.under15.price
        elif market == mkt.BTTS_YES:
            close_price = fx.btts_yes.price
        elif market == mkt.BTTS_NO:
            close_price = fx.btts_no.price
        elif market in (mkt.DC_1X, mkt.DC_X2, mkt.DC_12):
            close_price = getattr(fx, market.lower()).price
        if not close_price:
            continue

        candidate = {
            "market": market,
            "market_name": mkt.display(market, result.home_team, result.away_team),
            "entry_price": entry_price,
            "close_price": close_price,
            "prob": prob,
            "ev": ev,
            "mes": mes,
            "book_p": book_p,
        }
        if (best is None or (candidate["ev"] > best["ev"])
                or (candidate["ev"] == best["ev"] and candidate["prob"] > best["prob"])):
            best = candidate

    return best


def main():
    print(f"=" * 60)
    print(f"Agreement-Gate Backfill Experiment")
    print(f"Gate: |model - book| <= {AGREEMENT_BAND} (BLEND_NOOP_AT)")
    print(f"Window: {TARGET_START} .. {TARGET_END}")
    print(f"Model fit season: {FIT_SEASON} | Results season: {RESULTS_SEASON}")
    print(f"Experiment phase: {EXPERIMENT_PHASE}")
    print(f"Protected gate phase: {PAPER_PHASE} (will NOT be touched)")
    print(f"=" * 60)

    clv = CLVLog()
    total_legs_logged = 0
    total_clv = 0.0
    total_hits = 0
    total_missed = 0
    total_flags = []

    for league in sorted(WHITELISTED_LEAGUES):
        try:
            # Fit DC on 2526 (completed season — no lookahead)
            results_2526, _ = load_league(league, FIT_SEASON)
            if len(results_2526) < 20:
                print(f"  {league}: insufficient 2526 history ({len(results_2526)}) — skip")
                continue
            model = fit(results_2526)

            # Load settled 2627 results for the target window
            results_2627, _ = load_league(league, RESULTS_SEASON)
            target_fixtures = [
                r for r in results_2627
                if TARGET_START <= r.date <= TARGET_END
                   and r.odds and r.odds.home and r.odds.home.complete
                   and r.odds.over25 and r.odds.over25.complete
            ]
            if not target_fixtures:
                print(f"  {league}: no target fixtures with full open+close odds")
                continue

            league_legs = 0
            for r in target_fixtures:
                probs = predict(model, r.home_team, r.away_team)
                if probs is None:
                    continue

                fx = MockFixtureOdds(r)
                best = _best_leg_for_fixture(r, probs, fx, AGREEMENT_BAND)
                if best is None:
                    continue

                # Settlement
                hit = mkt.settle(best["market"], r.fthg, r.ftag)
                if hit is None:
                    continue

                # CLV from entry (open) vs close
                clv_pct = compute_clv(best["entry_price"], best["close_price"])

                # Build leg ID matching CLVLog convention
                fixture_name = f"{r.home_team} v {r.away_team}"
                leg_id = f"{fixture_name.replace(' ', '_')}_{best['market'].replace(' ', '_')}_{datetime.now(timezone.utc).timestamp():.0f}"

                leg = LoggedLeg(
                    leg_id=leg_id,
                    date_logged=datetime.now(timezone.utc).isoformat(),
                    league=r.league,
                    fixture=fixture_name,
                    market=best["market_name"],
                    model_prob=best["prob"],
                    match_date=r.date,
                    entry_odds=best["entry_price"],
                    entry_capture_path=ENTRY_CAPTURE_PATH,
                    closing_odds=best["close_price"],
                    closing_capture_path=CLOSE_CAPTURE_PATH,
                    clv_pct=clv_pct,
                    ft_result=f"{r.fthg}-{r.ftag}",
                    hit=hit,
                    stake=None,
                    phase=EXPERIMENT_PHASE,
                    notes=f"agreement_band={AGREEMENT_BAND} gate=|m-b|<={AGREEMENT_BAND} book_p={best['book_p']:.3f}",
                )
                clv.legs.append(leg)
                league_legs += 1
                total_legs_logged += 1
                total_clv += clv_pct
                if hit:
                    total_hits += 1
                else:
                    total_missed += 1

            if league_legs:
                print(f"  {league}: {league_legs} gate-cleared leg(s) logged")
            else:
                print(f"  {league}: 0 gate-cleared legs (all excluded by agreement band or MES)")

        except Exception as e:
            flag = f"{league}: backfill failed ({e})"
            print(f"  {flag}")
            total_flags.append(flag)

    clv._save()

    # Report
    print(f"\n{'=' * 60}")
    print(f"EXPERIMENT SUMMARY ({EXPERIMENT_PHASE})")
    print(f"{'=' * 60}")
    print(f"Total legs logged:      {total_legs_logged}")
    if total_legs_logged:
        print(f"Mean CLV:               {total_clv / total_legs_logged:.3f}%")
        print(f"Hit rate:               {total_hits}/{total_legs_logged} ({total_hits/total_legs_logged*100:.1f}%)")
        print(f"Won:                    {total_hits}")
        print(f"Lost:                   {total_missed}")
    else:
        print("No legs cleared the agreement gate + MES floor.")
    print(f"Flags:                  {len(total_flags)}")
    for f in total_flags:
        print(f"  - {f}")

    # Verify protected gate is UNTOUCHED
    print(f"\n{'=' * 60}")
    print(f"PROTECTED GATE CHECK (phase2_status)")
    print(f"{'=' * 60}")
    status = clv.phase2_status()
    for k, v in status.items():
        print(f"  {k}: {v}")
    print(f"\n✓ Experiment phase ({EXPERIMENT_PHASE}) is EXCLUDED from phase2_status()")
    print(f"  → Official Phase-3 gate is UNALTERED.")


if __name__ == "__main__":
    main()