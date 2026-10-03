"""
Simple fixture-list renderer for Telegram.

The full daily board is a probability / CLV artifact. This is the *simple*
view the Architect asked for: a date-ordered list of teams grouped by league
and kickoff time, WITH the model's pick + probability when available.

Data source: BoardFixture list (from output/produce_bet.py) — clean, verified,
with model probabilities and picks.

Kickoff times: PREFERRED source is the board fixture's own `kickoff_utc`
(the pipeline already resolved the real time from the SportyBet cache / ESPN
during the scan). If a fixture somehow has no `kickoff_utc`, we fall back to a
cross-cache name match for the TIME ONLY (league label ignored).

The fallback cache is `data/cache/sportybet/fixtures/` — the SAME SportyBet
Playwright cache the orchestrator reads (it carries `kickoff_utc` as a real ISO
timestamp, e.g. "2026-08-28T19:30:00Z"). Do NOT point this at
`booking/fixture_cache/`: that directory holds a *different*, low-quality
scrape (wrong clubs, non-ISO "HH:MM  ID:nnn" kickoffs) that is not a usable
time source.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Optional

# The authoritative SportyBet Playwright cache the orchestrator reads
# (booking/bridge.py _cache_path). Carries real ISO `kickoff_utc`.
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "sportybet" / "fixtures"

_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _hhmm_from_utc(utc: Optional[str]) -> Optional[str]:
    """Extract 'HH:MM' from an ISO timestamp; None if absent/garbled."""
    if not utc or len(utc) < 16:
        return None
    m = re.match(r"\d{4}-\d{2}-\d{2}T(\d{2}:\d{2})", utc)
    return m.group(1) if m else None


def _load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _normalize_name(name: str) -> str:
    """Lowercase, strip SRL/fc/fc suffixes and non-alphanum for matching."""
    n = name.lower()
    n = re.sub(r'\b(srl|fc|afc|cf|sc|ac)\b', '', n)
    return re.sub(r'[^a-z0-9]', '', n)


def _cache_kickoff(board_home: str, board_away: str) -> Optional[str]:
    """FALLBACK: find a kickoff TIME by matching home/away names ACROSS all
    cache files (league label ignored). Returns 'HH:MM' or None. Only used when
    the board fixture's own `kickoff_utc` is missing.

    Reads the real SportyBet Playwright cache (`data/cache/sportybet/fixtures/`),
    which stores `home_team`/`away_team` and a real ISO `kickoff_utc`
    (e.g. "2026-08-28T19:30:00Z"). Matches by name across every file; the time
    is the only thing taken — never the (unreliable) league label."""
    norm_h = _normalize_name(board_home)
    norm_a = _normalize_name(board_away)
    if not norm_h or not norm_a:
        return None
    for p in CACHE_DIR.glob("*.json"):
        data = _load_cache(p)
        for fx in data.get("fixtures", []):
            # Cache keys are home_team/away_team (bridge.py write path).
            ch = _normalize_name(fx.get("home_team", "") or fx.get("home", ""))
            ca = _normalize_name(fx.get("away_team", "") or fx.get("away", ""))
            # Direct match or cross-match (handles home/away swapped)
            if (ch == norm_h and ca == norm_a) or \
               (ch == norm_a and ca == norm_h):
                ko = _hhmm_from_utc(fx.get("kickoff_utc", "") or fx.get("kickoff", ""))
                if ko:
                    return ko
            # Containment: one name contains the other both ways
            h_contains = (norm_h in ch or ch in norm_h)
            a_contains = (norm_a in ca or ca in norm_a)
            if h_contains and a_contains:
                ko = _hhmm_from_utc(fx.get("kickoff_utc", "") or fx.get("kickoff", ""))
                if ko:
                    return ko
    return None


def _kickoff_for(bf, board_home: str, board_away: str) -> str:
    """Resolve a kickoff time for a fixture.

    1. PREFERRED: the board fixture's own `kickoff_utc` (resolved at scan time).
    2. FALLBACK: cross-cache name match for the time only.
    3. DEFAULT: '??:??' (HR35 — never fabricate a time)."""
    utc = getattr(bf, "kickoff_utc", None)
    hhmm = _hhmm_from_utc(utc)
    if hhmm:
        return hhmm
    return _cache_kickoff(board_home, board_away) or "??:??"


def _date_label(d: date) -> str:
    return f"{_WEEKDAYS[d.weekday()]} {d.day:02d} {_MONTHS[d.month - 1]} {d.year}"


def _pick_for(board: Optional[list], home: str, away: str) -> Optional[dict]:
    """Return dict with pick + all alt-market probabilities for a Home v Away
    pair from the BoardFixture list, or None if not found / no probs.

    PREFERS the best positive-EV alt market (best_market / best_mes_ev from
    BoardFixture) over the plain 1X2 result pick.

    Returned dict: {
        "label": str, "pct": int, "arrow": str,
        "p_home": float, "p_draw": float, "p_away": float,
        "p_over_15": float|None, "p_over_25": float|None,
        "p_over_35": float|None, "p_btts_yes": float|None,
    }
    """
    if not board:
        return None
    for bf in board:
        p = getattr(bf, "probs", None)
        if p is None:
            continue
        if (getattr(p, "home_team", "") == home
                and getattr(p, "away_team", "") == away):
            # Prefer the priced best market if it has positive EV
            best_market = getattr(bf, "best_market", None)
            best_mes_ev = getattr(bf, "best_mes_ev", None)
            best_model_prob = getattr(bf, "best_model_prob", None)

            if best_market and best_mes_ev is not None and best_mes_ev > 0:
                # Positive EV alt market available - use it
                label = best_market
                prob = best_model_prob or max(p.p_home, p.p_draw, p.p_away)
                # Arrow for alt markets
                if "win" in label.lower() or label == p.home_team:
                    arrow = "➡"
                elif "draw" in label.lower():
                    arrow = "⚪"
                elif "away" in label.lower() or label == p.away_team:
                    arrow = "🔁"
                elif "both teams" in label.lower() or "btts" in label.lower():
                    arrow = "🤝"
                else:
                    arrow = "📈"
            else:
                # Fallback: 1X2 result pick
                prob, side = max(
                    (p.p_home, "1"), (p.p_draw, "X"), (p.p_away, "2"),
                    key=lambda t: t[0])
                label = {"1": home, "X": "Draw", "2": away}[side]
                arrow = "➡" if label == home else ("⚪" if label == "Draw" else "🔁")

            return {
                "label": label,
                "pct": round(prob * 100),
                "arrow": arrow,
                "p_home": p.p_home,
                "p_draw": p.p_draw,
                "p_away": p.p_away,
                "p_over_15": getattr(p, "p_over_15", None),
                "p_over_25": getattr(p, "p_over_25", None),
                "p_over_35": getattr(p, "p_over_35", None),
                "p_btts_yes": getattr(p, "p_btts_yes", None),
            }
    return None


def _alt_markets(pick: dict) -> str:
    """Build the alt markets line: O1.5/O2.5/O3.5/BTTS with probabilities."""
    bits = []
    for key, short in [("p_over_15", "O1.5"), ("p_over_25", "O2.5"),
                       ("p_over_35", "O3.5"), ("p_btts_yes", "BTTS")]:
        val = pick.get(key)
        if val is not None:
            bits.append(f"{short} {round(val * 100)}%")
    return "  ·  ".join(bits) if bits else ""


def _normalize_fixture_name(fixture_str: str) -> tuple[str, str]:
    """Parse 'Home v Away (League)' -> (home, away)."""
    core = fixture_str.split("(")[0].strip()
    if " v " in core:
        home, away = core.split(" v ", 1)
        return home.strip(), away.strip()
    return "", ""


def _league_of(fixture_str: str) -> str:
    """Parse 'Home v Away (League)' -> 'League' (or 'Unknown')."""
    if "(" in fixture_str and ")" in fixture_str:
        return fixture_str.split("(")[-1].split(")")[0].strip()
    return "Unknown"


def render_fixture_list(board: Optional[list] = None,
                         cache_dir: Path = None) -> str:
    """Render fixtures from BoardFixture list with kickoff times.

    `board` is the authoritative fixture source (clean, verified). Leagues
    are listed alphabetically. Each fixture line shows the model PICK + win %
    plus alt market probabilities (O1.5/O2.5/O3.5/BTTS).

    Kickoff times: PREFERRED from each fixture's own `kickoff_utc` (resolved at
    scan time from the SportyBet cache / ESPN). Falls back to a cross-cache name
    match for the time ONLY when `kickoff_utc` is missing. League labels in the
    cache are unreliable, so they are never used for matching.

    `cache_dir` is kept for backwards compatibility but is IGNORED.
    """
    if not board:
        return "No board data provided. Run the daily pipeline first."

    # Build league -> list of (kickoff, home, away) from board
    leagues: dict[str, list[tuple[str, str, str]]] = {}

    for bf in board:
        fixture_str = getattr(bf, "fixture", "")
        home, away = _normalize_fixture_name(fixture_str)
        if not home or not away:
            continue
        league = _league_of(fixture_str)
        # Prefer the board's own resolved kickoff; fall back to cache time.
        ko = _kickoff_for(bf, home, away)
        leagues.setdefault(league, []).append((ko, home, away))

    if not leagues:
        return "No fixtures in board for today."

    today = date.today()
    lines = [f"📅  {_date_label(today)}   (PICK · win %  ·  alt markets)", ""]

    for lg in sorted(leagues):
        fx = sorted(leagues[lg], key=lambda t: t[0])
        lines.append(f"⚽  {lg}")
        for ko, home, away in fx:
            pick = _pick_for(board, home, away)
            if pick:
                pick_txt = f"   {pick['arrow']} {pick['label']} {pick['pct']}%"
                alt = _alt_markets(pick)
                if alt:
                    pick_txt += f"\n        {alt}"
            else:
                pick_txt = ""
            lines.append(f"   {ko}   {home:<24} v  {away:<24}{pick_txt}")
        lines.append("")
    return "\n".join(lines).rstrip()


if __name__ == "__main__":
    # Smoke test against the most recent board JSON if present.
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from datetime import date as _d
    from output.produce_bet import BoardFixture
    from engine.dixon_coles import FixtureProbabilities

    bd = Path(__file__).parent.parent / "output" / "boards"
    boards = sorted(bd.glob("board_*.json"))
    if not boards:
        print("No board JSON found for smoke test.")
    else:
        raw = json.loads(boards[-1].read_text(encoding="utf-8"))
        objs = []
        for e in raw.get("board", []):
            pd = e.get("probs")
            probs = (FixtureProbabilities(
                home_team=pd.get("home_team", ""), away_team=pd.get("away_team", ""),
                lambda_home=0.0, lambda_away=0.0,
                p_home=pd.get("p_home", 0.0), p_draw=pd.get("p_draw", 0.0),
                p_away=pd.get("p_away", 0.0),
                modal_scoreline=tuple(pd.get("modal_scoreline", [0, 0])),
                p_over_15=pd.get("p_over_15"), p_over_25=pd.get("p_over_25"),
                p_over_35=pd.get("p_over_35"), p_btts_yes=pd.get("p_btts_yes"))
                if pd else None)
            objs.append(BoardFixture(
                fixture=e.get("fixture", ""), probs=probs,
                verification=None, kickoff_utc=e.get("kickoff_utc")))
        print(render_fixture_list(board=objs))
