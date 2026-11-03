"""
TIP SITES — collect the free daily tips of football prediction websites and grade them on paper
(Architect 2026-11-03: "the football bots that do the scouting should check tips from prediction tip
sites too, so we can analyse them"). Paper only: nothing here selects a pick or stakes money, and no
finding is promoted without the Architect.

Only sites that let robots read the page are used. Forebet, PredictZ and WinDrawWin sit behind a
Cloudflare bot check (HTTP 403 on 2026-11-03) and are NOT worked around.

  vitibet   https://www.vitibet.com  quick tips: 1/X/2 percentages, a predicted score, a 1X2 / double chance tip
  statarea  https://www.statarea.com predictions (robots.txt: Allow /): a 1X2 / double chance tip, the 1/X/2
            percentages and the over 1.5/2.5/3.5 and both-teams-to-score percentages. The page draws its tips
            with JavaScript, so it is read with a headless browser (Playwright), once per run, like a visitor.

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
SITES = {"vitibet": "https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en",
         "statarea": "https://www.statarea.com/predictions"}
NEEDS_BROWSER = {"statarea"}

TIPS = {"1": ("1x2", "home"), "X": ("1x2", "draw"), "2": ("1x2", "away"), "0": ("1x2", "draw"),
        "1X": ("dc", "1x"), "10": ("dc", "1x"), "X2": ("dc", "x2"), "02": ("dc", "x2"), "12": ("dc", "12")}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_rendered(url: str) -> str:
    """The page after its JavaScript ran (headless Chromium). Playwright is imported here so the rest of
    the module works without it."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            pg = b.new_page(user_agent=UA)
            pg.goto(url, wait_until="networkidle", timeout=90000)
            return pg.content()
        finally:
            b.close()


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


def parse_statarea(page: str, now: datetime) -> list[dict]:
    """One slip per game that has not started. Times are in the page's own time zone (it names it)."""
    from zoneinfo import ZoneInfo
    tzname = re.search(r'class="zoneastext">\s*([A-Za-z_]+/[A-Za-z_]+)\s*<', page)
    try:
        tz = ZoneInfo(tzname.group(1)) if tzname else UTC
    except Exception:  # noqa: BLE001 — an unknown zone name: no tips rather than wrong kick-offs
        return []
    out = []
    for mid, block in re.findall(r'<div class="match" id="(\d+)">(.*?)<div class="userrow"', page, re.S):
        tip = re.search(r'<div class="tip">.*?<div class="type\d+">\s*([0-9X]{1,2})\s*<', block, re.S)
        when = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2})', block)
        home = re.search(r'class="hostteam">\s*<div class="goals">([^<]*)</div>\s*<div class="name"><a[^>]*>([^<]+)</a>', block)
        away = re.search(r'class="guestteam">\s*<div class="goals">([^<]*)</div>\s*<div class="name"><a[^>]*>([^<]+)</a>', block)
        if not (tip and when and home and away):
            continue
        if home.group(1).strip() not in ("-", "") or away.group(1).strip() not in ("-", ""):
            continue                             # a score is showing: started or finished
        kickoff = datetime.strptime(when.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=tz).astimezone(UTC)
        if kickoff <= now:
            continue
        mapped = TIPS.get(tip.group(1).upper())
        if mapped is None:
            continue
        vals = [int(v) / 100 for v in re.findall(r'<div class="value [a-z]\d+">(\d+)</div>', block)]
        leg = {"sport": "football", "home": htmlmod.unescape(home.group(2)).strip(),
               "away": htmlmod.unescape(away.group(2)).strip(),
               "kickoff": kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"), "market": mapped[0], "selection": mapped[1],
               "price": None, "text": f"statarea tip {tip.group(1).upper()}",
               "p": vals[0:3] if len(vals) >= 3 else [None, None, None], "score_tip": None}
        if len(vals) >= 11:                      # over 1.5 / 2.5 / 3.5, both teams to score: kept for later study
            leg["p_over"] = {"1.5": vals[6], "2.5": vals[7], "3.5": vals[8]}
            leg["p_btts"] = vals[9]
        out.append({"poster": "site:statarea", "post_url": f"site:statarea:{mid}", "official": False,
                    "posted_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "book": "site", "code": None,
                    "stated_odds": None, "legs": [leg]})
    return out


PARSERS = {"vitibet": parse_vitibet, "statarea": parse_statarea}


def collect(folder: Path, now: datetime, get=fetch, get_js=fetch_rendered) -> list[str]:
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
            rows = PARSERS[site]((get_js if site in NEEDS_BROWSER else get)(url), now)
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


ZERO_RUNS_ALARM = 2   # a site with no tips on this many runs in a row fails the workflow -> watchdog auto-fix


def health(folder: Path, notes: list[str]) -> list[str]:
    """Count each site's runs in a row with no tips (page changed, site down, blocked). Returns the sites that
    reached ZERO_RUNS_ALARM, so the run can fail loudly instead of quietly reading nothing (HR35)."""
    path = folder / "health.json"
    try:
        h = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        h = {}
    for site in SITES:
        line = next((n for n in notes if n.startswith(f"{site}:")), "")
        m = re.match(rf"{site}: (\d+) upcoming", line)
        h[site] = 0 if m and int(m.group(1)) > 0 else int(h.get(site, 0)) + 1
    path.write_text(json.dumps(h), encoding="utf-8")
    return [site for site in SITES if h[site] >= ZERO_RUNS_ALARM]


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
