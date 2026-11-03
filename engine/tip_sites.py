"""
TIP SITES — collect the free daily tips of football prediction websites and grade them on paper
(Architect 2026-11-03: "the football bots that do the scouting should check tips from prediction tip
sites too, so we can analyse them"). Paper only: nothing here selects a pick or stakes money, and no
finding is promoted without the Architect.

Only sites that let robots read the page are used. Forebet, PredictZ and WinDrawWin sit behind a
Cloudflare bot check (HTTP 403 on 2026-11-03) and are NOT worked around. Statarea draws its tips with
JavaScript (nothing in the HTML), so it is left out too.

  vitibet   https://www.vitibet.com  quick tips: 1/X/2 percentages, a predicted score, a 1X2 / double chance tip

Each tip becomes a one-leg "slip" in the engine/tipsters.py format (poster "site:<name>"), written to
data/tip_sites/slips_<day>.jsonl, so monitor/tipster_run.py grades it with the same strict Flashscore
match as the X slips. A tip is kept only if its game had NOT kicked off when it was read (no tips
collected after the fact). Only the pick, the percentages and the predicted score are stored, never
the site's text. The sites give no prices, so the study reports the hit rate and the Brier score of
the percentages, not a profit.
"""
from __future__ import annotations

import html as htmlmod
import json
import re
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
FOLDER = ROOT / "data" / "tip_sites"
UA = "Mozilla/5.0 (compatible; olp-xdv-tipsites/1.0; paper study)"
SITES = {"vitibet": "https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en"}

TIPS = {"1": ("1x2", "home"), "X": ("1x2", "draw"), "2": ("1x2", "away"), "0": ("1x2", "draw"),
        "1X": ("dc", "1x"), "10": ("dc", "1x"), "X2": ("dc", "x2"), "02": ("dc", "x2"), "12": ("dc", "12")}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def _pct(s: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", s)
    return float(m.group(1)) / 100 if m else None


def parse_vitibet(page: str, now: datetime) -> list[dict]:
    """One slip per upcoming game on the quick-tips page."""
    out = []
    for row in re.split(r"<a [^>]*class='livescore-match-row'", page)[1:]:
        fid = re.search(r"data-fid='(\d+)'", row)
        ko = re.search(r"data-time='([^']+)'", row)
        teams = [htmlmod.unescape(t).strip() for t in re.findall(r"class='livescore-team-name'>([^<]+)<", row)]
        tip = re.search(r"class='tip-indicator-circle'[^>]*>\s*([0-9X]{1,2})\s*<", row)
        if not (fid and ko and len(teams) >= 2 and tip):
            continue
        status = re.search(r"data-status='([^']+)'", row)
        if status and status.group(1) != "scheduled":
            continue
        try:
            kickoff = datetime.fromisoformat(ko.group(1)).astimezone(UTC)
        except ValueError:
            continue
        if kickoff <= now:                       # only tips read before the game starts
            continue
        mapped = TIPS.get(tip.group(1).upper())
        if mapped is None:
            continue
        probs = {h: _pct(v) for h, v in re.findall(
            r"class='prob-head'>\s*([12X])\s*</div>\s*<div class='prob-val'>([^<]+)<", row)}
        score = re.search(r"class='livescore-score-combined'[^>]*>\s*(\d+)-(\d+)\s*<", row)
        leg = {"sport": "football", "home": teams[0], "away": teams[1],
               "kickoff": kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"), "market": mapped[0], "selection": mapped[1],
               "price": None, "text": f"vitibet tip {tip.group(1).upper()}",
               "p": [probs.get("1"), probs.get("X"), probs.get("2")],
               "score_tip": [int(score.group(1)), int(score.group(2))] if score else None}
        out.append({"poster": "site:vitibet", "post_url": f"site:vitibet:{fid.group(1)}", "official": False,
                    "posted_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "book": "site", "code": None,
                    "stated_odds": None, "legs": [leg]})
    return out


PARSERS = {"vitibet": parse_vitibet}


def collect(folder: Path, now: datetime, get=fetch) -> list[str]:
    """Read every site once and append the new tips. Returns one note per site."""
    folder.mkdir(parents=True, exist_ok=True)
    seen = set()
    for p in folder.glob("slips_*.jsonl"):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    seen.add(json.loads(line)["post_url"])
                except (ValueError, KeyError):
                    pass
    notes = []
    for site, url in SITES.items():
        try:
            rows = PARSERS[site](get(url), now)
        except Exception as e:  # noqa: BLE001 — one site down must not stop the others
            notes.append(f"{site}: unavailable ({str(e)[:80]})")
            continue
        new = [r for r in rows if r["post_url"] not in seen]
        with (folder / f"slips_{now:%Y-%m-%d}.jsonl").open("a", encoding="utf-8") as f:
            for r in new:
                f.write(json.dumps(r, separators=(",", ":"), ensure_ascii=False) + "\n")
        seen |= {r["post_url"] for r in new}
        notes.append(f"{site}: {len(rows)} upcoming tips read, {len(new)} new")
    return notes


def _outcome(h: int, a: int) -> int:
    return 0 if h > a else 1 if h == a else 2


def summary(graded: list[dict]) -> dict:
    """Per site and tip type: tips graded, hit rate; Brier score of the 1/X/2 percentages and how often
    the site's own most-likely outcome happened; exact-score hits."""
    by = defaultdict(lambda: {"n": 0, "won": 0})
    sites = defaultdict(lambda: {"n": 0, "won": 0, "brier": 0.0, "nb": 0, "fav": 0, "exact": 0, "ns": 0})
    for g in graded:
        if not str(g.get("poster", "")).startswith("site:") or g.get("status") not in ("won", "lost"):
            continue
        site = g["poster"][5:]
        leg = (g.get("legs") or [{}])[0]
        won = g["status"] == "won"
        kind = f"{leg.get('market')} {leg.get('selection')}"
        by[(site, kind)]["n"] += 1
        by[(site, kind)]["won"] += won
        s = sites[site]
        s["n"] += 1
        s["won"] += won
        p, sc = leg.get("p") or [], leg.get("score")
        if sc and len(p) == 3 and None not in p and sum(p) > 0:
            o = _outcome(*sc)
            tot = sum(p)
            p = [x / tot for x in p]
            s["brier"] += sum((p[i] - (i == o)) ** 2 for i in range(3))
            s["nb"] += 1
            s["fav"] += max(range(3), key=lambda i: p[i]) == o
        if sc and leg.get("score_tip"):
            s["ns"] += 1
            s["exact"] += list(leg["score_tip"]) == list(sc)
    return {"sites": dict(sites), "kinds": {f"{k[0]} | {k[1]}": v for k, v in by.items()}}


def write_study(folder: Path, graded: list[dict], now: datetime) -> Path:
    s = summary(graded)
    lines = ["# Tip sites study (paper only)", "",
             f"Updated {now:%Y-%m-%d %H:%M} UTC by monitor/tip_sites_run.py. Tips read before kick-off, graded on "
             "Flashscore 90-minute results. No prices, so no profit figure. A uniform 1/3-1/3-1/3 guess scores a "
             "Brier of 0.667; lower is better.", "",
             "| Site | Graded | Tip hit rate | Brier (1X2 %) | Most-likely outcome right | Exact score |",
             "|---|---|---|---|---|---|"]
    for site, v in sorted(s["sites"].items()):
        lines.append(f"| {site} | {v['n']} | {v['won'] / v['n']:.0%} | "
                     f"{v['brier'] / v['nb']:.3f} | {v['fav'] / v['nb']:.0%} | "
                     f"{(v['exact'] / v['ns']) if v['ns'] else 0:.0%} |" if v["nb"] else
                     f"| {site} | {v['n']} | {v['won'] / v['n']:.0%} | PENDING | PENDING | PENDING |")
    if not s["sites"]:
        lines.append("| (none graded yet) | 0 | PENDING | PENDING | PENDING | PENDING |")
    lines += ["", "| Site / tip | Graded | Hit rate |", "|---|---|---|"]
    lines += [f"| {k} | {v['n']} | {v['won'] / v['n']:.0%} |" for k, v in sorted(s["kinds"].items())]
    out = folder / "TIP_SITES_STUDY.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
