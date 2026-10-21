"""
WEEKLY CLV SCORECARD (Architect, 2026-10-21: "add CLV with margins of error to the weekly
review and send it to WhatsApp every Monday").

Closing-line value is the headline: mean CLV per strategy with a 95% margin of error and
n, beside hit rate and ROI. Three books, split by strategy:
  * the board     -- graded singles by market family (CLV per pick), and every slip kind
                     (safe3 / accas / alts / combined / megas / clv_accas; a slip has no
                     closing line of its own, so its CLV shows n/a)
  * SportyBet     -- the placer's real bets by section, graded by the board's results
  * Matchbook     -- the live agent, from data/matchbook/summary.json (CLV and its spread)

Margin of error = 1.96 * sd / sqrt(n) (normal approximation); under THIN_N picks it is
flagged "thin". Reporting only: nothing here changes a pick, stake, threshold or gate.

    python scripts/clv_scorecard.py             # print, and write output/scorecard/latest.txt
    python scripts/clv_scorecard.py --no-write
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from math import sqrt
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PICKS = ROOT / "output" / "picks"
OUT = ROOT / "output" / "scorecard" / "latest.txt"
WINDOW_DAYS = 28
THIN_N = 30
MAX_CHARS = 3800          # the mirror's WhatsApp post limit is 4,000
SLIPS = (("safe3", "50%+ accas"), ("accas", "Accas"), ("alts", "Alt accas"),
         ("combined", "Combined"), ("megas", "Megas"), ("clv_accas", "CLV accas"))


def moe(n: int, sd: float | None) -> float | None:
    return 1.96 * sd / sqrt(n) if n >= 2 and sd is not None else None


def clv_cell(n: int, m: float | None, sd: float | None) -> str:
    """'CLV +1.2% ±2.1 ▲ n=85': mean CLV, 95% margin (pts), ▲/▼ when it excludes zero, n."""
    if not n or m is None:
        return "CLV n/a"
    e = moe(n, sd)
    if e is None:
        return f"CLV {m * 100:+.1f}% n={n} (thin)"
    mark = "▲" if m - e > 0 else "▼" if m + e < 0 else "○"
    return f"CLV {m * 100:+.1f}% ±{e * 100:.1f} {mark} n={n}" + (" (thin)" if n < THIN_N else "")


def _hit_roi(res: list[tuple[bool, float]]) -> str:
    """res = [(won, decimal odds)] -> 'hit 55% (6/11) · ROI +3.1%' at flat stakes."""
    n = len(res)
    if not n:
        return "no graded bets"
    won = sum(w for w, _ in res)
    roi = sum((o - 1) if w else -1 for w, o in res) / n
    return f"hit {won / n:.0%} ({won}/{n}) · ROI {roi * 100:+.1f}%"


def _docs(today: str, days: int, picks: Path) -> list[dict]:
    since = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
    out = []
    for p in sorted(picks.glob("picks_*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if since <= d.get("date", "") < today:
            out.append(d)
    return out


def _is_clv(s: dict) -> bool:
    return isinstance(s.get("clv"), (int, float))


def board_section(docs: list[dict]) -> list[str]:
    from engine.learning import family
    fams: dict = {}
    for d in docs:
        for s in d.get("singles", []):
            if s.get("result") in ("won", "lost") or _is_clv(s):
                fams.setdefault(family(s.get("market")), []).append(s)
    L = ["BOARD: singles by market family (CLV headline)"]
    rows = []
    for f, ss in fams.items():
        cl = [s["clv"] / 100 for s in ss if _is_clv(s)]
        res = [(s["result"] == "won", float(s.get("price") or 1)) for s in ss
               if s.get("result") in ("won", "lost")]
        m = mean(cl) if cl else None
        rows.append((-(m if m is not None else -9), f,
                     f"{f}: {clv_cell(len(cl), m, stdev(cl) if len(cl) > 1 else None)} · {_hit_roi(res)}"))
    L += [f"  {r}" for _k, _f, r in sorted(rows)[:10]] or ["  no singles in the window"]
    allc = [s["clv"] / 100 for ss in fams.values() for s in ss if _is_clv(s)]
    if allc:
        L.insert(1, f"  ALL: {clv_cell(len(allc), mean(allc), stdev(allc) if len(allc) > 1 else None)}")
    L.append("BOARD: slips by strategy (a slip has no closing line)")
    for key, label in SLIPS:
        res = [(x["result"] == "won", float(x.get("odds") or 1))
               for d in docs for x in d.get(key, []) if x.get("result") in ("won", "lost")]
        if res:
            L.append(f"  {label}: CLV n/a · {_hit_roi(res)}")
    return L


def sportybet_section(today: str, days: int, picks: Path, data: Path) -> list[str]:
    from monitor.sportybet_ledger import board_results
    since = (date.fromisoformat(today) - timedelta(days=days)).isoformat()
    groups: dict = {}
    for f in sorted(data.glob("placed_*.json")):
        try:
            placed = json.loads(f.read_text(encoding="utf-8"))
            if not (since <= placed["date"] < today):
                continue
            res = board_results(json.loads((picks / f"picks_{placed['date']}.json").read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError):
            continue
        for b in placed.get("bets") or []:
            got = res.get(str(b.get("code", "")).upper())
            if b.get("status") == "placed" and got in ("won", "lost"):
                groups.setdefault(b.get("section") or "?", []).append(
                    (got == "won", float(b.get("odds") or 1), float(b.get("units") or 1)))
    L = ["SPORTYBET: real bets by section (stake-weighted ROI)"]
    for sec, rs in sorted(groups.items()):
        units = sum(u for _w, _o, u in rs)
        roi = sum(u * (o - 1) if w else -u for w, o, u in rs) / units
        won = sum(w for w, _o, _u in rs)
        L.append(f"  {sec}: CLV n/a · hit {won / len(rs):.0%} ({won}/{len(rs)}) · ROI {roi * 100:+.1f}%")
    return L if len(L) > 1 else L + ["  no settled bets in the window"]


def matchbook_section(summary: Path) -> list[str]:
    L = ["MATCHBOOK: live agent, all time (no £ shown)"]
    try:
        g = json.loads(summary.read_text(encoding="utf-8"))["groups"]
    except (OSError, ValueError, KeyError):
        return L + ["  summary not available"]
    for key in ("all", "source: framework pick", "source: framework rated market",
                "source: oracle (blind LLM)"):
        s = g.get(key)
        if not s or not s.get("settled"):
            continue
        roi = f" · ROI {s['roi'] * 100:+.1f}%" if s.get("roi") is not None else ""
        L.append(f"  {'ALL' if key == 'all' else key.replace('source: ', '')}: "
                 f"{clv_cell(s.get('clv_n') or 0, s.get('mean_clv'), s.get('clv_sd'))} · "
                 f"hit {s['won'] / s['settled']:.0%} ({s['won']}/{s['settled']}){roi}")
    return L


def scorecard(today: str | None = None, days: int = WINDOW_DAYS, picks: Path = PICKS,
              data: Path = ROOT / "data" / "sportybet",
              mb: Path = ROOT / "data" / "matchbook" / "summary.json") -> str:
    today = today or date.today().isoformat()
    L = [f"📊 CLV SCORECARD · {days} days to {today}",
         "CLV = price taken vs closing price; ± is the 95% margin; ▲ clearly positive, "
         "▼ clearly negative, ○ not yet distinguishable from zero"]
    for sec in (lambda: board_section(_docs(today, days, picks)),
                lambda: sportybet_section(today, days, picks, data),
                lambda: matchbook_section(mb)):
        try:
            L += sec()
        except Exception as e:  # noqa: BLE001
            L.append(f"(section unavailable: {e})")
    text = "\n".join(L)
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS - 20].rsplit("\n", 1)[0] + "\n...(trimmed)"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=WINDOW_DAYS)
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    text = scorecard(days=a.days)
    print(text)
    if not a.no_write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
