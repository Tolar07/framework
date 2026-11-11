"""
Football player predictions from the predicted line-up (framework #557, Event models #3). RECORD-ONLY / SHADOW.

Architect 2026-11-11: "understand each player and what each player can do on the field, understanding the line-up".
For each player in a side's predicted XI: chance of a card, expected fouls, tackles, shots, shots on target and the
chance of scoring (anytime scorer). It picks nothing, stakes nothing and moves no other number.

How:
- History: data/match_players/<month>.jsonl (every player line FotMob gives, #556): minutes, cards, fouls, tackles,
  shots, shots on target. A stat FotMob did not give for a player is absent, never 0 (HR35).
- Rate: per-90 rate of the player, shrunk to his position group (goalkeeper / outfield, or the position FotMob names)
  with SHRINK_MIN pseudo-minutes: (events + group_rate * SHRINK_MIN/90) / ((minutes + SHRINK_MIN)/90).
- Expected minutes: his mean minutes in the games he started (DEFAULT_MINUTES when unknown).
- **Agrees with the team model:** the XI's raw player numbers are scaled so that they add up to the team total of
  engine/event_model.py for that side (times the starters' historical share of the team total, XI_SHARE, since
  substitutes take the rest) -- `tests/player_model_test.py` checks the sums. Cards are also scaled by the referee's
  strictness (his cards per match against the league's, shrunk with REF_SHRINK matches).
- Scoring: the team's expected goals (the board's Dixon-Coles number) split by each player's share of the XI's
  expected shots on target: chance = 1 - exp(-xG_team * share).
- Nothing here is believed until backtest/player_study.py (walk-forward, beats the player's own season rate) lets it
  through; output is labelled `shadow` until then.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAYERS_DIR = ROOT / "data" / "match_players"
SHRINK_MIN = 900.0         # pseudo-minutes at the position-group rate behind every player rate (10 games)
DEFAULT_MINUTES = 78.0     # an XI player with no history
REF_SHRINK = 10.0          # pseudo-matches at the league mean behind every referee's card rate
MIN_STARTER_MINUTES = 45   # a player who played this long counts as a starter when the lineup flag is missing

# our event -> FotMob player stat keys, first one present wins. (Keys are FotMob's; "cards" come from the match events.)
ALIAS: dict[str, tuple[str, ...]] = {
    "fouls": ("fouls_committed", "fouls", "Fouls"),
    "tackles": ("tackles_won", "tackles", "matchstats.headers.tackles"),
    "shots": ("total_shots", "shots", "ShotsTotal"),
    "sot": ("ShotsOnTarget", "shots_on_target", "shotsontarget"),
}
EVENTS = ("cards", "fouls", "tackles", "shots", "sot")
# the team-model event each player event must add up to
TEAM_EVENT = {"cards": "yellow", "fouls": "fouls", "tackles": "tackles", "shots": "shots", "sot": "sot"}


def _num(v) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).split()[0].rstrip("%"))
    except (ValueError, IndexError):
        return None


def minutes_of(r: dict) -> float | None:
    for k in ("minutes_played", "minutes", "MinutesPlayed"):
        v = _num(r.get(k))
        if v is not None:
            return v
    return None


def group_of(r: dict) -> str:
    if r.get("gk"):
        return "GK"
    return str(r.get("position") or r.get("role") or "outfield")


def stat_of(r: dict, ev: str) -> float | None:
    """The player's count of one event in one match, or None when FotMob did not give it."""
    if ev == "cards":
        y, rd = _num(r.get("yellow")), _num(r.get("red"))
        # no card event line means no card (the match events list every card); a player with minutes always has a
        # known card count, so absence is 0 here and only here
        return (y or 0.0) + (rd or 0.0)
    for k in ALIAS[ev]:
        v = _num(r.get(k))
        if v is not None:
            return v
    return None


def load_players(paths: Iterable[Path] | None = None) -> list[dict]:
    """Every saved player line that has minutes, oldest first."""
    rows = []
    for p in sorted(paths if paths is not None else PLAYERS_DIR.glob("*.jsonl")):
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            m = minutes_of(r)
            if r.get("date") and r.get("id") is not None and m is not None and m > 0:
                rows.append({**r, "_min": m})
    rows.sort(key=lambda r: r["date"])
    return rows


@dataclass
class PlayerModel:
    group_rate: dict = field(default_factory=dict)    # group -> {ev: per-90 rate}
    pooled_rate: dict = field(default_factory=dict)   # ev -> per-90 rate (all outfield+GK)
    players: dict = field(default_factory=dict)       # id -> {"min", "ev": {ev: [sum, minutes_with_stat]}, "starts": [mins]}
    xi_share: dict = field(default_factory=dict)      # ev -> starters' share of the team total
    n_lines: int = 0

    @classmethod
    def fit(cls, rows: list[dict], before: str | None = None) -> PlayerModel:
        """Everything known before `before` (an ISO date; None = all)."""
        use = [r for r in rows if before is None or r["date"] < before]
        m = cls(n_lines=len(use))
        gsum: dict = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
        psum: dict = defaultdict(lambda: [0.0, 0.0])
        team_tot: dict = defaultdict(lambda: defaultdict(float))     # (fotmob_id, side) -> ev -> total
        xi_tot: dict = defaultdict(lambda: defaultdict(float))
        for r in use:
            g, mins = group_of(r), r["_min"]
            rec = m.players.setdefault(r["id"], {"name": r.get("name"), "group": g, "ev": {}, "starts": []})
            rec["group"] = g
            if mins >= MIN_STARTER_MINUTES:
                rec["starts"].append(mins)
            key = (r.get("fotmob_id"), r.get("side") or r.get("team"))
            for ev in EVENTS:
                v = stat_of(r, ev)
                if v is None:
                    continue
                s = rec["ev"].setdefault(ev, [0.0, 0.0])
                s[0] += v
                s[1] += mins
                gsum[g][ev][0] += v
                gsum[g][ev][1] += mins
                psum[ev][0] += v
                psum[ev][1] += mins
                team_tot[key][ev] += v
                if mins >= MIN_STARTER_MINUTES:
                    xi_tot[key][ev] += v
        for g, evs in gsum.items():
            m.group_rate[g] = {ev: 90 * s[0] / s[1] for ev, s in evs.items() if s[1] > 0}
        m.pooled_rate = {ev: 90 * s[0] / s[1] for ev, s in psum.items() if s[1] > 0}
        for ev in EVENTS:
            t = sum(v.get(ev, 0.0) for v in team_tot.values())
            x = sum(v.get(ev, 0.0) for v in xi_tot.values())
            if t > 0:
                m.xi_share[ev] = x / t
        return m

    def rate(self, pid, group: str, ev: str) -> tuple[float | None, float]:
        """(per-90 rate shrunk to the position group, minutes behind it); None when nothing is known for the event."""
        g = self.group_rate.get(group, {}).get(ev, self.pooled_rate.get(ev))
        if g is None:
            return None, 0.0
        s = (self.players.get(pid) or {}).get("ev", {}).get(ev)
        mins = s[1] if s else 0.0
        ev_sum = s[0] if s else 0.0
        return (ev_sum + g * SHRINK_MIN / 90) / ((mins + SHRINK_MIN) / 90), mins

    def own_rate(self, pid, ev: str) -> float | None:
        """The baseline: the player's own raw per-90 rate so far, None if he has no minutes."""
        s = (self.players.get(pid) or {}).get("ev", {}).get(ev)
        return 90 * s[0] / s[1] if s and s[1] > 0 else None

    def expected_minutes(self, pid) -> float:
        st = (self.players.get(pid) or {}).get("starts") or []
        return sum(st[-10:]) / len(st[-10:]) if st else DEFAULT_MINUTES

    def predict_side(self, xi: list[dict], team_totals: dict, xg: float | None = None, ref_cards: float = 1.0) -> dict:
        """xi: [{"id", "name", "gk"?, "position"?}]; team_totals: {team-model event: this side's expected total}.
        Returns {"players": [...], "pending": [events not predictable]}. Per event the XI's numbers add up to
        team total * XI_SHARE (cards also * ref_cards)."""
        out = [{"id": p.get("id"), "name": p.get("name"), "group": group_of(p), "exp_minutes": 0.0, "events": {}}
               for p in xi]
        for o in out:
            o["exp_minutes"] = round(self.expected_minutes(o["id"]), 1)
        pending = []
        for ev in EVENTS:
            tv = team_totals.get(TEAM_EVENT[ev])
            if tv is None:
                pending.append(ev)
                continue
            target = tv * self.xi_share.get(ev, 0.9) * (ref_cards if ev == "cards" else 1.0)
            raw = []
            for o in out:
                r, mins = self.rate(o["id"], o["group"], ev)
                raw.append(None if r is None else r * o["exp_minutes"] / 90)
            tot = sum(x for x in raw if x is not None)
            if tot <= 0:
                pending.append(ev)
                continue
            scale = target / tot
            for o, x in zip(out, raw, strict=True):
                if x is not None:
                    o["events"][ev] = x * scale
        for o in out:
            ev = o["events"]
            if "cards" in ev:
                ev["card_chance"] = 1 - math.exp(-ev["cards"])
        if xg is not None and all("sot" in o["events"] for o in out):
            tot = sum(o["events"]["sot"] for o in out) or 1.0
            for o in out:
                o["events"]["scorer_chance"] = 1 - math.exp(-xg * o["events"]["sot"] / tot)
        for o in out:
            o["events"] = {k: round(v, 4) for k, v in o["events"].items()}
            o["matches_behind"] = int(((self.players.get(o["id"]) or {}).get("ev", {}).get("fouls") or [0, 0])[1] // 90)
        return {"players": out, "pending": pending}


def referee_factor(matches: list[dict], referee_name: str | None, league: str | None, before: str | None = None) -> float:
    """Cards per match of this referee over the league's, shrunk to 1.0 with REF_SHRINK matches. Match rows are the
    data/match_stats lines (engine.event_model.load_history): "referee": {"name"}, stats "yellow": [h, a]."""
    use = [r for r in matches if (before is None or r["date"] < before) and "yellow" in r.get("stats", {})]
    lg = [r for r in use if r.get("league") == league] or use
    if not lg or not referee_name:
        return 1.0
    mean = sum(sum(r["stats"]["yellow"]) for r in lg) / len(lg)
    mine = [sum(r["stats"]["yellow"]) for r in use if (r.get("referee") or {}).get("name") == referee_name]
    if mean <= 0 or not mine:
        return 1.0
    return (sum(mine) + REF_SHRINK * mean) / ((len(mine) + REF_SHRINK) * mean)
