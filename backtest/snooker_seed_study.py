"""
SNOOKER ELO SEED STUDY (framework#340, record-only, shadow).

Problem: the live snooker Elo (data/multisport/snooker/elo.json) holds only the few games the board has seen, and a
player needs ms.MIN_GAMES rated games, so the shadow board's `model` is empty on almost every game. 6590 World Snooker
Tour matches exist (data/snooker/results.json). This study builds a SHADOW Elo from them (same K and min games as the
board, every match scored before it is learned) and reports, next to the live one:
  * name bridge: history writes 'Kyren Wilson' (or surname-first 'Chen Zifan'), SportyBet 'Wilson, Kyren' (key
    'wilson k'). A board player maps to a history player only if exactly ONE history player fits; more than one is
    AMBIGUOUS, none UNMATCHED (HR35: never guessed).
  * coverage: board games where the live Elo gives a chance vs where the seeded shadow Elo would.
  * agreement with the price on those games, and Brier on graded ones (PENDING under MIN_GRADED, HR35).
Nothing here changes the board, a pick rule, a stake, a bar or the live switch: the live Elo file is not written.

  python backtest/snooker_seed_study.py      writes backtest/SNOOKER_SEED_STUDY.md
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import exchange as ex  # noqa: E402
from engine import multisport as ms  # noqa: E402

OUT = ROOT / "backtest" / "SNOOKER_SEED_STUDY.md"
DATA = ROOT / "data" / "snooker" / "results.json"
MIN_GRADED = 30


def board_keys(name: str) -> set[str]:
    """Board-style keys ('surname initial') a history name could be written as: first-last and surname-first."""
    t = ex.norm(name).split()
    if len(t) < 2:
        return set()
    return {f"{t[-1]} {t[0][:1]}", f"{t[0]} {t[1][:1]}"}


def seed_elo(rows: list[dict]) -> dict:
    elo = {"ratings": {}, "games": {}, "seen": [], "brier": [0.0, 0]}
    ms.learn(elo, [r for r in rows if r.get("winner") in (1, 2)])
    return elo


def name_index(elo: dict) -> dict[str, set[str]]:
    idx: dict[str, set[str]] = {}
    for n in elo["ratings"]:
        for k in board_keys(n):
            idx.setdefault(k, set()).add(n)
    return idx


def resolve(board_name: str, idx: dict[str, set[str]]):
    """(history key or None, 'ok' | 'ambiguous' | 'unmatched')."""
    c = idx.get(ms.norm(board_name), set())
    if len(c) == 1:
        return next(iter(c)), "ok"
    return None, ("ambiguous" if c else "unmatched")


def seeded_p(elo: dict, idx: dict, home: str, away: str):
    """(Home chance or None, reason)."""
    h, st_h = resolve(home, idx)
    a, st_a = resolve(away, idx)
    if h is None or a is None or h == a:
        return None, (st_h if h is None else st_a if a is None else "ambiguous")
    if elo["games"].get(h, 0) < ms.MIN_GAMES or elo["games"].get(a, 0) < ms.MIN_GAMES:
        return None, "few games"
    return 1 / (1 + 10 ** ((elo["ratings"][a] - elo["ratings"][h]) / 400)), "ok"


def _price_fair(g: dict):
    """(fair chance of Home from the winner market's last look, did Home win) or (None, None)."""
    sides = g.get("sides") or {}
    last = {k: (v.get("last") or v.get("first") or {}) for k, v in sides.items()}
    prices = {k: v["price"] for k, v in last.items() if v.get("price")}
    for key, s in sides.items():
        sp = ms.split_key(key)
        if sp[1] in ms.WINNER_MARKETS and sp[3].lower() == "home":
            q = last[key].get("fair") or (ms.devig(key, prices) if key in prices else None)
            return q, s.get("won")
    return None, None


def study(rows: list[dict], docs: list[tuple[str, dict]], live_elo: dict) -> dict:
    elo = seed_elo(rows)
    idx = name_index(elo)
    games, players = [], {}
    for _d, doc in docs:
        for g in (doc.get("games") or {}).values():
            games.append(g)
            for nm in (g.get("home"), g.get("away")):
                if nm:
                    players[nm] = resolve(nm, idx)[1]
    out = {"history_players": len(elo["ratings"]), "history_games": len(elo["seen"]),
           "players": len(players), "board_games": len(games),
           "player_status": {s: sum(v == s for v in players.values()) for s in ("ok", "ambiguous", "unmatched")},
           "live_covered": 0, "seeded_covered": 0, "why_not": {}, "diffs": [], "graded": []}
    for g in games:
        if ms.elo_p(live_elo, g.get("home") or "", g.get("away") or "") is not None:
            out["live_covered"] += 1
        p, why = seeded_p(elo, idx, g.get("home") or "", g.get("away") or "")
        if p is None:
            out["why_not"][why] = out["why_not"].get(why, 0) + 1
            continue
        out["seeded_covered"] += 1
        q, won = _price_fair(g)
        if q is not None:
            out["diffs"].append(abs(p - q))
            if won in (0, 1):
                out["graded"].append((p, q, float(won)))
    return out


def render(rows: list[dict], docs: list[tuple[str, dict]], live_elo: dict, now: datetime) -> str:
    L = ["# Snooker Elo seed study (framework#340)", "",
         f"Made {now:%Y-%m-%d %H:%M} UTC by `backtest/snooker_seed_study.py`. Record only: the live Elo is not written.", ""]
    if not rows or not docs:
        return "\n".join(L + ["NO DATA - PENDING (needs data/snooker/results.json and the shadow board's files).", ""])
    r = study(rows, docs, live_elo)
    n = r["board_games"]
    ps = r["player_status"]
    L += [f"Shadow Elo from history: {r['history_games']} matches, {r['history_players']} players "
          f"(K={ms.ELO_K:g}, min {ms.MIN_GAMES} games, each match scored before it is learned).", "",
          f"- Board games recorded: **{n}** ({r['players']} players: {ps['ok']} matched to one history player, "
          f"{ps['ambiguous']} ambiguous, {ps['unmatched']} unmatched).",
          f"- Games where the LIVE Elo gives a chance: **{r['live_covered']}** of {n}.",
          f"- Games where the SEEDED Elo would: **{r['seeded_covered']}** of {n}. Left out: "
          + (", ".join(f"{k} {v}" for k, v in sorted(r["why_not"].items())) or "none") + "."]
    d = r["diffs"]
    L.append("- Seeded Elo vs the price's fair chance on %d games: mean gap " % len(d)
             + (f"{100 * sum(d) / len(d):.1f} pts." if d else "PENDING (no price)."))
    g = r["graded"]
    if len(g) < MIN_GRADED:
        L.append(f"- Brier on graded games: PENDING ({len(g)} graded, need {MIN_GRADED}); the price stays the default.")
    else:
        be = sum((p - y) ** 2 for p, _q, y in g) / len(g)
        bq = sum((q - y) ** 2 for _p, q, y in g) / len(g)
        L.append(f"- Brier on {len(g)} graded games: seeded Elo {be:.4f} vs price {bq:.4f}.")
    L += ["", "Reading: the model only becomes usable on the board if the bridge matches players and the Brier above "
          "beats the price once enough games are graded. Until then nothing is switched (the blend-weight study "
          "decides, `backtest/multisport_blend_study.py`). Record only: no rule, stake, bar or live switch changed.", ""]
    return "\n".join(L)


def run(now: datetime | None = None) -> str:
    rows = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else []
    text = render(rows, ms.load_all("snooker"), ms.load_elo("snooker"), now or datetime.now(UTC))
    OUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(run())
