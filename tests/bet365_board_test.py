"""
Locks the bet365 board (output/bet365_board.py, standing order 29): picks are
limited to bets bet365 offers, a SportyBet-only bet gives way to the likeliest
bet365 one, nothing is silently dropped, no price is invented, and every pick
carries its country + league.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import full_markets as fm
from engine.dixon_coles import FixtureProbabilities
from output import bet365_board as b365
from output.produce_bet import BoardFixture
from pipeline.odds import MarketQuote
from verification.id403 import Tier, VerificationResult


def _p(home, away):
    return FixtureProbabilities(home_team=home, away_team=away, lambda_home=1.4,
        lambda_away=1.1, p_home=0.45, p_draw=0.28, p_away=0.27, p_over_15=0.75,
        p_over_25=0.5, p_over_35=0.28, p_btts_yes=0.5)


_V = VerificationResult(tier=Tier.SINGLE_SOURCE, value=1.9,
                        factors={"independent_domains": ["x"]}, note="")


def _c(win, key, price, model=None, market=None, ev=0.0):
    return (win, ev, key, model if model is not None else win,
            market if market is not None else win, MarketQuote(price=price))


def _bf(fixture, home, away, key, price, chance, pool, certainty="HIGH"):
    bf = BoardFixture(fixture, _p(home, away), _V, on_deploy_shortlist=True,
                      best_market_key=key, best_price=price, best_model_prob=chance,
                      certainty=certainty)
    bf.cand_pool = pool
    return bf


K = fm.key
# --- what bet365 offers, in bet365's words ---
assert b365.bet365_name(K(34, "", "No"), "Azerbaijan", "Lithuania") is None, \
    "bet365 has no 'win to nil — no'"
assert b365.bet365_name(K(34, "", "Yes"), "Azerbaijan", "Lithuania") == "To Win to Nil: Lithuania"
assert b365.bet365_name(K(31, "", "No"), "Kosovo", "Austria") == "Team Goals: Austria Over 0.5", \
    "a clean sheet 'no' is the other team's Over 0.5 goals"
assert b365.bet365_name(K(16, "hcp=-1.5", "Away (+1.5)"), "Girona", "Mallorca") \
    == "Asian Handicap: Mallorca +1.5"
assert b365.bet365_name(K(14, "hcp=0:2", "Away (0:2)"), "Girona", "Mallorca") \
    == "Handicap Result: Mallorca +2"
assert b365.bet365_name(K(11, "", "Home"), "Girona", "Mallorca") == "Draw No Bet: Girona"
assert b365.bet365_name(K(29, "", "No"), "A", "B") == "Both Teams to Score: No"
assert b365.bet365_name("DC_1X", "Wales", "Denmark") == "Double Chance: Wales or draw"
# The full betting market (Architect 2026-10-04), Double Chance & Goals included
H, A = "Castellon", "Ceuta"
for k, want in [
    (K(547, "total=1.5", "Home/Away & Over 1.5"), "Double Chance & Goals: Castellon or Ceuta & Over 1.5"),
    (K(546, "", "Home/Draw & Yes"), "Double Chance & Both Teams to Score: Castellon or Draw & Yes"),
    (K(36, "total=2.5", "Over 2.5 & Yes"), "Goals & Both Teams to Score: Over 2.5 & Yes"),
    (K(37, "total=1.5", "Home & Over 1.5"), "Result & Total Goals: Castellon & Over 1.5"),
    (K(548, "", "1-3"), "Multigoals: 1-3"),
    (K(25, "", "2-3"), "Total Goals Range: 2-3"),
    (K(21, "", "2"), "Exact Total Goals: 2"),
    (K(23, "", "1-2"), "Team Total Goals: Castellon 1-2"),
    (K(26, "", "Odd"), "Goals Odd/Even: Odd"),
    (K(30, "", "Only Home"), "Teams to Score: Only Castellon"),
    (K(12, "", "Away"), "Castellon No Bet: Ceuta"),
    (K(13, "", "Draw"), "Ceuta No Bet: Draw"),
]:
    got_name = b365.bet365_name(k, H, A)
    assert got_name == want, f"{k}: {got_name!r} != {want!r}"
# Every market the ladder scores is on the bet365 list
assert set(fm.LADDER_MARKET_IDS) <= set(b365.BET365_MARKETS) | {31, 32, 33, 34}, \
    "the full betting market is on the bet365 list"
print("bet365 market names: OK")

# --- deploy-at price: break-even, rounded up, never under the 1.20 floor ---
assert b365.deploy_at(0.82) == 1.22 and b365.deploy_at(0.95) == 1.20 and b365.deploy_at(0.5) == 2.00
print("deploy-at price: OK")

# --- picking ---
same = _bf("Sociedad B v Granada (La Liga 2)", "Sociedad B", "Granada",
           K(10, "", "Home or Away"), 1.33, 0.74, [])
swap = _bf("Azerbaijan v Lithuania (UEFA Nations League)", "Azerbaijan", "Lithuania",
           K(34, "", "No"), 1.20, 0.82,
           [_c(0.82, K(34, "", "No"), 1.20),
            _c(0.80, K(18, "total=2.5", "Under 2.5"), 1.22),
            _c(0.79, K(10, "", "Draw or Away"), 1.25, model=0.78, market=0.79)],
           certainty="MEDIUM")
none = _bf("Malta v Andorra (UEFA Nations League)", "Malta", "Andorra",
           K(33, "", "No"), 1.21, 0.80, [_c(0.80, K(33, "", "No"), 1.21)])
risk = _bf("Chelsea v Bournemouth (Premier League)", "Chelsea", "Bournemouth",
           K(33, "", "No"), 1.40, 0.76,
           [_c(0.76, K(33, "", "No"), 1.40),
            _c(0.75, K(1, "", "Home"), 1.45),
            _c(0.72, K(18, "total=1.5", "Over 1.5"), 1.30)])
risk.team_news = {"lineup_type": "predicted",
                  "home": {"name": "Chelsea", "missing_share": 0.40,
                           "missing": [{"name": "Player X"}]},
                  "away": {"name": "Bournemouth", "missing_share": 0.0, "missing": []}}
off = BoardFixture("Lech v Legia (Ekstraklasa)", None, _V)   # not on the deploy list

pk = b365.choose(same)
assert pk["same"] and pk["name"] == "Double Chance: Sociedad B or Granada" \
    and pk["chance"] == 0.74, "a pick bet365 offers stays the same pick"
pk = b365.choose(swap)
assert not pk["same"] and pk["name"] == "Double Chance: Lithuania or draw", \
    "a SportyBet-only pick gives way to the likeliest bet365 one, Under-goals last"
assert pk["sb_price"] == 1.25 and pk["certainty"] == "HIGH"
assert b365.choose(none) is None, "nothing winnable on bet365 -> no bet365 pick"
pk = b365.choose(risk)
assert pk["name"] == "Goals Over/Under: Over 1.5", \
    "a bet365 option the team news flags gives way to one it doesn't touch"
combo = _bf("Castellon v Ceuta (La Liga 2)", "Castellon", "Ceuta",
            K(547, "total=1.5", "Home/Away & Over 1.5"), 1.21, 0.75, [])
pk = b365.choose(combo)
assert pk["same"] and pk["name"] == "Double Chance & Goals: Castellon or Ceuta & Over 1.5", \
    "a Double Chance & Goals pick stays the same pick on bet365"
got, missing = b365.picks([same, swap, none, risk, off])
assert len(got) == 3 and missing == [none], "deploy fixtures only; none silently dropped"
print("bet365 picks: OK")

# --- the board text ---
same.kickoff_utc = "2026-10-04T16:30:00.000Z"
txt = b365.render([same, swap, none, risk, off], board_date="2026-10-04")
assert "Times are kickoff, Lagos time (WAT)" in txt and " • 17:30 Sociedad B v Granada — " in txt, \
    "order 28: each bet365 single shows its kickoff (Lagos)"
assert " • PENDING " in txt, "HR35: no kickoff time reads PENDING, never a guess"
assert txt.startswith("##########OLP XDV · BET365#########")
assert "Sun 04 Oct 2026" in txt and "sent to you only" in txt
assert "\U0001F1EA\U0001F1F8 Spain · La Liga 2" in txt, "picks grouped under country + league"
assert "\U0001F3C6 UEFA Nations League" in txt
assert "deploy at 1.36+" in txt and "SportyBet @1.33" in txt, "deploy-at + SportyBet reference"
assert "≠ Double Chance: Lithuania or draw" in txt
assert "(SportyBet pick: Lithuania Win to Nil — no — not on bet365)" in txt
assert "No bet365 pick (1)" in txt and "Malta v Andorra" in txt, "HR35: shown, never dropped"
assert "bet365 Acca A" in txt, "picks grouped into accas to build by hand"
assert ("DRAFT" in txt) == (not b365.MENU_CONFIRMED)
assert "Lech v Legia" not in txt
assert "@1.2" not in txt.split("bet365 SINGLES")[1].replace("SportyBet @", ""), \
    "no bet365 price is ever printed — only SportyBet's, labelled"
empty = b365.render([off], board_date="2026-10-04")
assert "No bet365 pick today" in empty
print("bet365 board render: OK")
print("bet365_board_test: OK")
