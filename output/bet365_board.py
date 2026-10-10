"""
THE bet365 BOARD — the day's picks restricted to bets bet365 offers, sent to
the Architect on its own (standing order 29, Architect 2026-10-04).

WHY A SEPARATE BOARD
  SportyBet and bet365 do not offer the same bets. SportyBet quotes both sides
  of "Win to Nil" (yes / no); bet365 only offers "<team> to win to nil", so a
  SportyBet pick of "Lithuania Win to Nil — no" has no bet365 equivalent.

ONE PIPELINE, TWO OUTPUTS
  Fixtures, model, verification, team news and learning are the same for both
  books, so this board is built from the SAME run as the SportyBet board — no
  second pipeline to drift out of step. Only the menu of bets differs:
    * the SportyBet pick is kept when bet365 offers it (same chance, certainty);
    * otherwise the fixture's likeliest OTHER winnable outcome (the run's
      cand_pool: >= 50%, SportyBet price inside 1.20–2.00) that bet365 offers,
      Under-goals last (Architect preference), never one the team news flags;
    * a fixture with no such outcome is listed as having no bet365 pick —
      shown, never silently dropped (HR35).

PRICES — NONE INVENTED
  There is no free bet365 price feed for these markets (standing order 27: no
  paid API), so the board does not print a bet365 price. It prints DEPLOY AT
  (the trigger price of the Telegram Output Spec, 2026-09-17): the lowest
  bet365 price worth taking — break-even for our chance, never below the 1.20
  floor. SportyBet's real price is shown for reference.

NO BOOKING CODES
  bet365 has no SportyBet-style share codes; picks are found by hand, so each
  one is grouped under its country and league (standing order 28).

THE MENU is the full betting market (Architect 2026-10-04) except win to
nil "no". The bet365 NAMES are a draft until the Architect confirms them
against the app (MENU_CONFIRMED). Live capital stays SportyBet-only
(standing order 26).
"""
from __future__ import annotations

import math
import re
from datetime import date

from engine import competitions as comp
from engine import full_markets as fm
from engine import markets as mkt
from engine.slate import AGREE_PP, CERTAINTY_HIGH_PP, DEPLOY_MIN_MODEL_PROB, DEPLOY_ODDS_MIN
from output.produce_bet import ACCA_LEG_MIN, ACCA_MAX, ACCA_MIN, _acca_name, _split_sizes, kickoff

# Flip to True once the Architect has checked the bet365 NAMES against the app.
MENU_CONFIRMED = False

# SportyBet ladder market id -> bet365 market, with the SAME settlement.
# Architect 2026-10-04: the FULL betting market is on bet365 — every market
# the ladder scores (engine/full_markets.LADDER_MARKET_IDS) — with one
# exception the Architect named: win to nil is offered only as "<team> to win
# to nil" (yes), never "no". 31/32 (clean sheet) read as the other team's
# goals Over/Under 0.5, which settles the same way.
BET365_MARKETS = {
    1: "Full Time Result",
    10: "Double Chance",
    11: "Draw No Bet",
    12: "No Bet",                       # "<home> No Bet": void if home wins
    13: "No Bet",                       # "<away> No Bet": void if away wins
    14: "Handicap Result",
    16: "Asian Handicap",
    18: "Goals Over/Under",
    19: "Team Goals",
    20: "Team Goals",
    21: "Exact Total Goals",
    23: "Team Total Goals",
    24: "Team Total Goals",
    25: "Total Goals Range",
    26: "Goals Odd/Even",
    29: "Both Teams to Score",
    30: "Teams to Score",
    36: "Goals & Both Teams to Score",
    37: "Result & Total Goals",
    546: "Double Chance & Both Teams to Score",
    547: "Double Chance & Goals",
    548: "Multigoals",
}

UNDER_PREF_PP = 0.03     # same Under-goals preference as run_daily's selection


def bet365_name(key: str, home: str, away: str) -> str | None:
    """How a pick reads on bet365, or None when bet365 does not offer it."""
    if not key:
        return None
    if not key.startswith("SB:"):
        name = mkt.display(key, home, away)
        if key in (mkt.HOME, mkt.DRAW, mkt.AWAY):
            return f"Full Time Result: {name.replace(' to win', '')}"
        if key in (mkt.DC_1X, mkt.DC_X2, mkt.DC_12):
            return f"Double Chance: {name}"
        if key in (mkt.OVER_15, mkt.UNDER_15, mkt.OVER_25, mkt.UNDER_25,
                   mkt.OVER_35, mkt.UNDER_35):
            return f"Goals Over/Under: {name.replace(' goals', '')}"
        if key in (mkt.BTTS_YES, mkt.BTTS_NO):
            return f"Both Teams to Score: {'Yes' if key == mkt.BTTS_YES else 'No'}"
        return None
    pk = fm.parse_key(key)
    if not pk:
        return None
    mid, spec, outcome = pk
    sp = fm._spec(spec)
    team = {"home": home, "away": away}
    o = outcome.strip()
    if mid in (31, 32):          # clean sheet = the other side's goals 0.5
        other = away if mid == 31 else home
        side = "Under" if o.lower() == "yes" else "Over" if o.lower() == "no" else None
        return f"Team Goals: {other} {side} 0.5" if side else None
    if mid in (33, 34):          # bet365: "<team> to win to nil" — yes only
        return (f"To Win to Nil: {home if mid == 33 else away}"
                if o.lower() == "yes" else None)
    if mid not in BET365_MARKETS:
        return None
    market = BET365_MARKETS[mid]
    if mid == 14:                # European 3-way handicap "x:y"
        m = re.fullmatch(r"(\d+):(\d+)", sp.get("hcp", ""))
        who = o.split(" (")[0].lower()
        if not m or who not in ("home", "draw", "away"):
            return None
        line = int(m.group(1)) - int(m.group(2))     # home's start, in goals
        if who == "draw":
            return f"{market}: Tie ({home} {line:+d})"
        return f"{market}: {team[who]} {line if who == 'home' else -line:+d}"
    if mid == 16:                # Asian handicap "Away (+1.5)"
        m = re.fullmatch(r"(home|away)\s*\(([+-]?[\d.]+)\)", o.lower())
        if not m:
            return None
        return f"{market}: {team[m.group(1)]} {float(m.group(2)):+g}"
    if mid in (19, 20):
        return f"{market}: {home if mid == 19 else away} {o}"
    if mid in (1, 11):
        named = team.get(o.lower()) or ("Draw" if mid == 1 and o.lower() == "draw" else None)
        return f"{market}: {named}" if named else None
    if mid in (18, 26, 29):
        return f"{market}: {o[:1].upper() + o[1:].lower()}"
    if mid in (12, 13):          # "<team> No Bet": stake back if that team wins
        named = team.get(o.lower()) or ("Draw" if o.lower() == "draw" else None)
        return f"{home if mid == 12 else away} {market}: {named}" if named else None
    if mid in (21, 25, 548):     # total-goals counts / ranges, e.g. "1-3", "7+"
        return f"{market}: {o}"
    if mid in (23, 24):
        return f"{market}: {home if mid == 23 else away} {o}"
    if mid == 30:
        named = {"none": "No goal", "only home": f"Only {home}", "only away": f"Only {away}",
                 "both teams": "Both teams"}.get(o.lower())
        return f"{market}: {named}" if named else None
    return f"{market}: {fm.display_key(key, home, away)}"


def deploy_at(chance: float) -> float:
    """Lowest price worth taking: break-even for the chance, rounded UP to
    the next 0.01, never below the deploy floor."""
    return max(DEPLOY_ODDS_MIN, math.ceil(100.0 / chance - 1e-9) / 100.0)


def _certainty(model_p, market_p) -> str:
    if model_p is None or market_p is None:
        return "LOW"
    gap = abs(model_p - market_p)
    return "HIGH" if gap <= CERTAINTY_HIGH_PP else "MEDIUM" if gap <= AGREE_PP else "LOW"


def _is_under(k: str) -> bool:
    return "|Under" in k or "& Under" in k or k in (mkt.UNDER_25, mkt.UNDER_15, mkt.UNDER_35)


def choose(bf) -> dict | None:
    """This fixture's bet365 pick, or None when bet365 offers nothing winnable."""
    p = bf.probs
    if p is None or not bf.best_market_key:
        return None
    home, away = p.home_team, p.away_team
    sb_pick = mkt.display(bf.best_market_key, home, away)
    name = bet365_name(bf.best_market_key, home, away)
    if name:
        flagged = bf.news_level in ("CAUTION", "RISK")
        return {"bf": bf, "name": name, "chance": bf.best_model_prob,
                "sb_price": bf.best_price, "certainty": bf.certainty or "LOW",
                "same": True, "sb_pick": sb_pick,
                "news": f"{bf.news_level}: {bf.news_note}" if flagged else None}
    pool = [c for c in (getattr(bf, "cand_pool", None) or [])
            if c[0] >= DEPLOY_MIN_MODEL_PROB and bet365_name(c[2], home, away)]
    if not pool:
        return None
    # Team news (order 24): a pick that depends on a weakened team gives way
    # to one the news doesn't touch; if every option is touched, say so.
    news = getattr(bf, "team_news", None)
    levels: dict[str, dict] = {}
    if news:
        from engine import team_news as tn
        levels = {c[2]: tn.assess(c[2], news) for c in pool}
        safe = [c for c in pool if levels[c[2]]["level"] not in ("CAUTION", "RISK")]
        pool = safe or pool
    top = max(c[0] for c in pool)
    near = [c for c in pool if c[0] >= top - UNDER_PREF_PP and not _is_under(c[2])]
    c = max(near or pool, key=lambda c: (c[0], c[1]))
    lv = levels.get(c[2], {})
    return {"bf": bf, "name": bet365_name(c[2], home, away), "chance": c[0],
            "sb_price": c[5].price, "certainty": _certainty(c[3], c[4]),
            "same": False, "sb_pick": sb_pick,
            "news": (f"{lv['level']}: {lv['note']}"
                     if lv.get("level") in ("CAUTION", "RISK") else None)}


def picks(board: list) -> tuple[list[dict], list]:
    """(bet365 picks, deploy fixtures with no bet365 pick) for the board."""
    got, missing = [], []
    for bf in board:
        if not bf.on_deploy_shortlist or bf.probs is None:
            continue
        pk = choose(bf)
        if pk:
            got.append(pk)
        else:
            missing.append(bf)
    return got, missing


_RULE = "─" * 34
_BAR = "=" * 34


def render(board: list, board_date: str | None = None, run_id: str | None = None) -> str:
    """The bet365 board text (Telegram-ready, phone width)."""
    day = (date.fromisoformat(board_date) if board_date
           else date.today()).strftime("%a %d %b %Y")
    got, missing = picks(board)
    out = ["##########OLP XDV · BET365#########", _BAR, "",
           f"\U0001F4C5  {day} — bet365 board (sent to you only)",
           f"Run ID: {run_id or 'PENDING'} (same run as the SportyBet board)",
           "Times are kickoff, Lagos time (WAT)", "",
           "Same fixtures, model and checks as the SportyBet board; each pick is "
           "limited to bets bet365 offers.",
           "• No booking codes on bet365 — find each match by country → league → match.",
           "• DEPLOY AT = the lowest bet365 price worth taking (break-even for the "
           f"chance, never below {DEPLOY_ODDS_MIN:.2f}). Below it, skip the bet. "
           "SportyBet's price is shown for reference.",
           "• ≠ = not the SportyBet pick (bet365 doesn't offer that one)."]
    if not MENU_CONFIRMED:
        out.append("⚠ bet365 market NAMES are a DRAFT — check them against your bet365 "
                   "app and tell Claude any that read differently there.")
    try:   # BOTH TEAMS TO SCORE (Architect 2026-10-10: "for SportyBet and bet365")
        from output.produce_bet import _build_btts
        _bt = _build_btts(board)
    except Exception:  # noqa: BLE001
        _bt = []
    if _bt:
        out += ["", _RULE, "bet365 BOTH TEAMS TO SCORE (same games as SportyBet TABLE 3D)", _RULE]
        for _bf, _pk, _ch, _k, _pr in _bt[0][1]:
            out.append(f"• {kickoff(_bf)} {_bf.fixture.split(' (')[0]} — Both Teams to Score: Yes "
                       f"({round(_ch*100)}%) · DEPLOY AT {deploy_at(_ch):.2f} · SportyBet {_pr:.2f}")
    out += ["", _RULE, "bet365 SINGLES", _RULE]
    if not got:
        out.append("No bet365 pick today — nothing on bet365's list clears 50% in the "
                   "1.20–2.00 band.")
    groups: dict[str, list[dict]] = {}
    for pk in got:
        groups.setdefault(comp.label(comp.league_of(pk["bf"].fixture), flag=True),
                          []).append(pk)
    for where, pks in groups.items():
        out += ["", where]
        for pk in sorted(pks, key=lambda x: -x["chance"]):
            sb = f"SportyBet @{pk['sb_price']:.2f}" if pk["sb_price"] else "SportyBet price PENDING"
            out.append(f" • {kickoff(pk['bf'])} {pk['bf'].fixture.rsplit(' (', 1)[0]} — "
                       f"{'' if pk['same'] else '≠ '}{pk['name']}")
            out.append(f"   {round(pk['chance'] * 100)}% · deploy at {deploy_at(pk['chance']):.2f}+ "
                       f"· {sb} · {pk['certainty']}")
            if not pk["same"]:
                out.append(f"   (SportyBet pick: {pk['sb_pick']} — not on bet365)")
            if pk["news"]:
                out.append(f"   ⚠ {pk['news']}")

    # order 40: only 75%+ picks go into an acca, 3 legs each
    legs = sorted((pk for pk in got if pk["chance"] >= ACCA_LEG_MIN), key=lambda x: -x["chance"])
    sizes = _split_sizes(len(legs), ACCA_MIN, ACCA_MAX)
    if sizes:
        out += ["", _RULE, "bet365 ACCAS", "(build by hand on bet365, strongest legs first)",
                _RULE]
        i = 0
        for n, size in enumerate(sizes):
            g = legs[i:i + size]
            i += size
            combo, floor = 1.0, 1.0
            for pk in g:
                combo *= pk["chance"]
                floor *= deploy_at(pk["chance"])
            out.append(f"{_acca_name(n).replace('Acca', 'bet365 Acca')} · {len(g)} legs · "
                       f"chance {round(combo * 100)}% · deploy at {floor:.2f}+ combined")
            for pk in g:
                out.append(f"   • {comp.where(pk['bf'].fixture)} — {pk['name']} "
                           f"({round(pk['chance'] * 100)}%)")

    if missing:
        out += ["", f"No bet365 pick ({len(missing)}) — its SportyBet pick isn't on bet365 "
                    f"and nothing else on bet365's list clears 50% in the band:"]
        for bf in missing:
            sb = mkt.display(bf.best_market_key, bf.probs.home_team, bf.probs.away_team)
            out.append(f"   • {comp.where(bf.fixture)} — SportyBet pick: {sb}")

    out += ["", _BAR,
            "Honest edge: not a demonstrated edge · Capital: Architect only.",
            "Live capital test is SportyBet only (standing order 26) — this board is "
            "for reference.",
            _BAR]
    return "\n".join(out)
