"""
SHADOW: home-edge Elo next to the live multi-sport Elo (framework#344, rugby first). Record only.

backtest/RUGBY_STUDY.md found the live Elo (no home edge) does not beat a flat home-edge baseline, while the same
Elo with +70 Elo points for the home side did (held-out Brier 0.1965 vs 0.2206). This keeps a second rating table
with that edge, learning from the same finished games, and scores BOTH on every game where both have a pre-game
chance (walk-forward: chance first, then the update). It never touches a pick, a stake, a bar or the live Elo;
the numbers are written to the sport's scoreboard.json under "home_edge_shadow" for the Architect to judge.
A missing table reads PENDING (no games scored yet), never invented.
"""
from __future__ import annotations

import json
from pathlib import Path

from engine import multisport as ms

EDGE = {"rugby": 70.0}      # Elo points added to the home side's rating in the CANDIDATE only
# Second candidate: per-league home edge (backtest/RUGBY_COMBINED_STUDY.md, held-out 2020-2025 Brier 0.1844 vs 0.1965
# for the flat +70). Matched on words in the Flashscore league name; any other league keeps the flat edge.
LEAGUE_EDGE = {"rugby": [("champions", 130.0), ("premiership", 130.0), ("top 14", 200.0), ("urc", 160.0),
                         ("united rugby", 160.0)]}


def league_edge(sport: str, league: str | None) -> float | None:
    """Per-league edge for this game, the flat edge when the league is unknown, None for a sport with no edge."""
    base = EDGE.get(sport)
    if base is None:
        return None
    name = (league or "").lower()
    for key, e in LEAGUE_EDGE.get(sport, []):
        if key in name:
            return e
    return base


def path(sport: str) -> Path:
    return ms.DATA_DIR / sport / "elo_home_edge.json"


def load(sport: str) -> dict:
    try:
        st = json.loads(path(sport).read_text(encoding="utf-8"))
        for k, v in (("lg_ratings", {}), ("lg_games", {}), ("lg_n", 0), ("lg_live_sq", 0.0), ("lg_sq", 0.0)):
            st.setdefault(k, v)
        return st
    except (OSError, ValueError):
        return {"ratings": {}, "games": {}, "seen": [], "n": 0, "live_sq": 0.0, "cand_sq": 0.0,
                "lg_ratings": {}, "lg_games": {}, "lg_n": 0, "lg_live_sq": 0.0, "lg_sq": 0.0}


def save(sport: str, st: dict) -> None:
    p = path(sport)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")


def _p(rh: float, ra: float, edge: float) -> float:
    return 1 / (1 + 10 ** ((ra - rh - edge) / 400))


def learn(sport: str, st: dict, games: list[dict], live_elo: dict) -> int:
    """Score then update, oldest first. The live chance comes from `live_elo` AS IT WAS before these
    games, so call this BEFORE ms.learn(live_elo, games). Returns games added."""
    edge = EDGE.get(sport)
    if edge is None:
        return 0
    seen, n = set(st["seen"]), 0
    live = {"ratings": dict(live_elo["ratings"]), "games": dict(live_elo["games"])}
    for g in sorted(games, key=lambda x: x.get("kickoff_utc") or ""):
        gid = f"{g['home']}|{g['away']}|{g.get('kickoff_utc') or ''}"
        if gid in seen or g.get("winner") not in (1, 2):
            continue
        h, a = ms.norm(g["home"]), ms.norm(g["away"])
        y = 1.0 if g["winner"] == 1 else 0.0
        rh, ra = st["ratings"].get(h, ms.ELO_START), st["ratings"].get(a, ms.ELO_START)
        if st["games"].get(h, 0) >= ms.MIN_GAMES and st["games"].get(a, 0) >= ms.MIN_GAMES:
            pl = ms.elo_p(live, g["home"], g["away"])
            if pl is not None:
                st["n"] += 1
                st["live_sq"] += (pl - y) ** 2
                st["cand_sq"] += (_p(rh, ra, edge) - y) ** 2
        # per-league candidate: its own rating table, scored on the games where it AND the live Elo are rated
        lgE = league_edge(sport, g.get("league"))
        lh, la = st["lg_ratings"].get(h, ms.ELO_START), st["lg_ratings"].get(a, ms.ELO_START)
        if st["lg_games"].get(h, 0) >= ms.MIN_GAMES and st["lg_games"].get(a, 0) >= ms.MIN_GAMES:
            pl = ms.elo_p(live, g["home"], g["away"])
            if pl is not None:
                st["lg_n"] += 1
                st["lg_live_sq"] += (pl - y) ** 2
                st["lg_sq"] += (_p(lh, la, lgE) - y) ** 2
        el = _p(lh, la, lgE)
        st["lg_ratings"][h] = round(lh + ms.ELO_K * (y - el), 2)
        st["lg_ratings"][a] = round(la - ms.ELO_K * (y - el), 2)
        st["lg_games"][h] = st["lg_games"].get(h, 0) + 1
        st["lg_games"][a] = st["lg_games"].get(a, 0) + 1
        e = _p(rh, ra, edge)
        st["ratings"][h] = round(rh + ms.ELO_K * (y - e), 2)
        st["ratings"][a] = round(ra - ms.ELO_K * (y - e), 2)
        st["games"][h] = st["games"].get(h, 0) + 1
        st["games"][a] = st["games"].get(a, 0) + 1
        # keep the live-side copy moving so later games in this batch see the same pre-game live chance
        vh, va = live["ratings"].get(h, ms.ELO_START), live["ratings"].get(a, ms.ELO_START)
        eL = _p(vh, va, 0.0)
        live["ratings"][h] = round(vh + ms.ELO_K * (y - eL), 2)
        live["ratings"][a] = round(va - ms.ELO_K * (y - eL), 2)
        live["games"][h] = live["games"].get(h, 0) + 1
        live["games"][a] = live["games"].get(a, 0) + 1
        seen.add(gid)
        n += 1
    st["seen"] = sorted(seen)[-20000:]
    return n


def summary(sport: str, st: dict) -> dict:
    n = st["n"]
    if not n:
        return {"status": "PENDING", "edge": EDGE.get(sport), "scored": 0, "per_league": {"status": "PENDING", "scored": 0}}
    lb, cb = st["live_sq"] / n, st["cand_sq"] / n
    m = st.get("lg_n", 0)
    pl = ({"status": "RECORD", "scored": m, "live_brier": round(st["lg_live_sq"] / m, 4),
           "candidate_brier": round(st["lg_sq"] / m, 4), "candidate_better": st["lg_sq"] < st["lg_live_sq"]}
          if m else {"status": "PENDING", "scored": 0})
    return {"status": "RECORD", "edge": EDGE.get(sport), "scored": n, "live_brier": round(lb, 4),
            "candidate_brier": round(cb, 4), "candidate_better": cb < lb, "per_league": pl}
