"""Study exercise board through the engine (14 Oct 2026; same method as 13 Oct, plus the
13 Oct lessons as study filters: no team Under on a side the strength-adjusted profile
expects to score more than 1.3, and no match Under when the profile reads BTTS yes / Over). Every open SportyBet
outcome of every fixture of the day is scored the way run_daily scores the
full ladder: P(WIN) on a scoreline grid (a void is not a win), the bookmaker's
grid fitted to its own 1X2 + O/U 2.5, the model's grid (Championship only,
from today's ledger) blended at 25% (order 18), the line-consistency guard,
band 1.20-2.00 and >= 50% to WIN (orders 3, 4). Then one market per fixture,
none repeated, BTTS included. Then accas by orders 40/42 and booking codes."""
import json, sys, uuid, datetime as dt, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import numpy as np
from scipy.optimize import minimize, linear_sum_assignment
from scipy.stats import poisson
from pipeline import odds_sportybet as sb
from pipeline import sportybet_booking as bk
from engine import full_markets as fm, half, calibration as cal
HERE = Path(__file__).parent
SCR = HERE
from data import team_profiles as tp, league_strength as ls
PROF, STR = tp.load(), ls.load()

sb._CACHE = Path("/tmp/claude-0/sb_events_engine_1014.json")   # a fresh SportyBet fetch for this run
RUN_ID = "STUDY-" + uuid.uuid4().hex[:8]
by_tid, flags = sb._load_all_events()
FETCHED = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
ledger = json.loads(subprocess.run(["git", "-C", "/home/user/framework", "show",
                    "origin/main:output/picks/picks_2026-10-14.json"], capture_output=True, text=True).stdout)
MODEL = {r["fixture"]: r["p"] for r in ledger["rated"] if r["src"] == "model"}

G = np.arange(11)
def fit(ph, pd, pa, pov):
    def grid(x):
        lh, la = np.exp(x); m = np.outer(poisson.pmf(G, lh), poisson.pmf(G, la)); return m / m.sum()
    T = np.add.outer(G, G)
    def loss(x):
        m = grid(x)
        return ((np.tril(m, -1).sum()-ph)**2 + (np.triu(m, 1).sum()-pa)**2 + (np.trace(m)-pd)**2 + (m[T > 2].sum()-pov)**2)
    r = minimize(loss, np.log([1.4, 1.1]), method="Nelder-Mead", options={"xatol": 1e-6, "fatol": 1e-12, "maxiter": 600})
    return np.exp(r.x), grid(r.x)
def devig(ps):
    inv = [1/p for p in ps]; s = sum(inv); return [i/s for i in inv]

FAM = {"1": "1X2", "10": "Double chance", "11": "Draw no bet", "12": "Home/Away no bet", "13": "Home/Away no bet",
       "14": "European handicap", "16": "Asian handicap", "18": "Over/Under", "19": "Team goals", "20": "Team goals",
       "21": "Exact goals / range", "25": "Exact goals / range", "23": "Team multigoals", "24": "Team multigoals",
       "26": "Odd/Even", "29": "Both teams to score", "30": "Which team scores", "33": "Win to nil", "34": "Win to nil",
       "36": "Total & BTTS", "37": "1X2 & total", "546": "Double chance & BTTS", "547": "Double chance & total",
       "548": "Multigoals", "60": "1st half 1X2", "63": "1st half double chance", "64": "1st half draw no bet"}
COMPS = {"sr:tournament:7": ("UEFA Champions League", "Champions League"), "sr:tournament:18": ("England · Championship", "Championship")}
NAME = {"Blackburn Rovers": "Blackburn", "Charlton Athletic": "Charlton", "Millwall FC": "Millwall", "Swansea City": "Swansea",
        "Wrexham AFC": "Wrexham", "West Bromwich Albion": "West Brom", "Birmingham City": "Birmingham",
        "Preston North End": "Preston", "Stoke City": "Stoke", "Middlesbrough FC": "Middlesbrough"}
fixtures, rejected_lines = [], 0
for tid, (comp, league) in COMPS.items():
    for e in by_tid.get(tid, []):
        ko = dt.datetime.fromtimestamp(e["estimateStartTime"]/1000, dt.UTC)
        if ko.strftime("%Y-%m-%d") != "2026-10-14":
            continue
        mk = sb.parse_markets(e)
        get = lambda mid, spec, o: next((float(x["odds"]) for m in mk if str(m["id"]) == mid and m["specifier"] == spec
                                         for x in m["outcomes"] if x["desc"] == o and x.get("odds")), None)
        H, D, A = get("1", "", "Home"), get("1", "", "Draw"), get("1", "", "Away")
        OV, UN = get("18", "total=2.5", "Over 2.5"), get("18", "total=2.5", "Under 2.5")
        ph, pd, pa = devig([H, D, A]); pov = devig([OV, UN])[0]
        mlam, mgrid = fit(ph, pd, pa, pov)
        name = f"{NAME.get(e['homeTeamName'], e['homeTeamName'])} v {NAME.get(e['awayTeamName'], e['awayTeamName'])}"
        mp = next((v for k, v in MODEL.items() if k.split(" v ")[0] in name or name.split(" v ")[0] in k), None)
        dlam, dgrid = fit(mp[0], mp[1], mp[2], mp[4]) if mp else (None, None)
        th, ta = tp.find(PROF, e["homeTeamName"]), tp.find(PROF, e["awayTeamName"])
        read = (tp.profile_read(th, ta, ls.gap(STR, th.get("stats_league"), ta.get("stats_league")))
                if th and ta else {"lean": "PENDING — team not in the profile database"})
        hh, ah = read.get("home_goals_hint"), read.get("away_goals_hint")
        cands, lesson_cut = [], 0
        for m in mk:
            mid = str(m["id"])
            if mid not in FAM:
                continue
            for o in m["outcomes"]:
                if not o.get("odds") or o.get("id") is None:
                    continue
                price = float(o["odds"]); desc = o["desc"]
                if mid == "30" and desc.lower().startswith("both"):
                    continue                                    # same bet as BTTS yes
                if desc.startswith("Under") and ((mid == "19" and hh and hh > 1.3) or (mid == "20" and ah and ah > 1.3)
                                                 or (mid == "18" and read["lean"].startswith("BTTS yes"))):
                    lesson_cut += 1                             # 13 Oct lesson: no Under against the profile
                    continue
                if mid in ("60", "63", "64"):                   # first half: league half-share of each grid
                    def h1(lam):
                        a, b, c = half.model_probs(lam[0], lam[1], league)
                        side = {"Home": a, "Draw": b, "Away": c}
                        if mid == "60": return side.get(desc, 0.0), 0.0
                        if mid == "63": return sum(side.get(x.strip(), 0) for x in desc.split(" or ")), 0.0
                        return side.get(desc, 0.0), b
                    mkw = h1(mlam); mdw = h1(dlam) if dlam is not None else mkw
                else:
                    rule = fm.rule_for(int(mid), m["specifier"], desc)
                    if rule is None:
                        continue
                    mkw = fm.evaluate(mgrid, rule); mdw = fm.evaluate(dgrid, rule) if dgrid is not None else mkw
                    if mkw[1] < 1 and mkw[0] / (1 - mkw[1]) - 1/price > fm.LINE_TOLERANCE:
                        rejected_lines += 1; continue           # line-consistency guard
                if dgrid is not None and mid not in ("60", "63", "64"):   # model BTTS/goals calibrated, as run_daily
                    mdw = (cal.model_prob(f"SB:{mid}|{m['specifier']}|{desc}", mdw[0]), mdw[1])
                win = mkw[0] + 0.25 * (mdw[0] - mkw[0]); void = mkw[1] + 0.25 * (mdw[1] - mkw[1])
                cands.append({"fam": FAM[mid], "mid": mid, "spec": m["specifier"], "mdesc": m["desc"], "pick": desc,
                              "price": price, "win": win, "void": void, "mkt_win": mkw[0],
                              "model_win": mdw[0] if dgrid is not None else None,
                              "ev": win * price + void - 1,
                              "sel": {"eventId": e["eventId"], "marketId": m["id"], "specifier": m["specifier"],
                                      "outcomeId": o["id"]}})
        fixtures.append({"comp": comp, "match": name, "ko": ko, "cands": cands, "src": "model+market" if mp else "market",
                         "profile": read, "lesson_cut": lesson_cut})
fixtures.sort(key=lambda f: (f["ko"], f["match"]))
fams = sorted({c["fam"] for f in fixtures for c in f["cands"]})
best = {}
for i, f in enumerate(fixtures):
    for c in f["cands"]:
        if 1.20 <= c["price"] <= 2.00 and c["win"] >= 0.50:
            k = (i, c["fam"])
            if k not in best or (c["win"], c["ev"]) > (best[k]["win"], best[k]["ev"]):
                best[k] = c
cost = np.full((len(fixtures), len(fams)), 1e6)
for (i, fam), c in best.items():
    cost[i, fams.index(fam)] = -(c["win"] + (0.5 if fam == "Both teams to score" else 0))
rows, cols = linear_sum_assignment(cost)
picks = {r: best[(r, fams[c])] for r, c in zip(rows, cols) if cost[r, c] < 1e6}
out = {"run_id": RUN_ID, "fetched_at": FETCHED, "flags": flags, "lines_rejected": rejected_lines, "legs": []}
for i, f in enumerate(fixtures):
    p = picks.get(i)
    btts = {c["pick"]: c for c in f["cands"] if c["mid"] == "29"}
    out["legs"].append({"match": f["match"], "comp": f["comp"], "ko": f["ko"].isoformat(), "src": f["src"], "pick": p,
                        "btts": btts, "profile": f["profile"], "lesson_cut": f["lesson_cut"]})
json.dump(out, open(SCR / "engine_board.json", "w"), indent=1, default=str)
print(RUN_ID, FETCHED, flags, "lines rejected by guard:", rejected_lines)
for l in out["legs"]:
    p = l["pick"]; ko = (dt.datetime.fromisoformat(l["ko"]) + dt.timedelta(hours=1)).strftime("%H:%M")
    if not p:
        print(ko, l["match"], "NO PICK"); continue
    mw = f"{p['model_win']:.0%}" if p["model_win"] is not None else "—"
    print(f"{ko} | {l['match'][:30]:30} | {p['fam'][:22]:22} | {p['mdesc'][:30]} {p['spec']}: {p['pick']} | @{p['price']:.2f} | WIN {p['win']:.0%} void {p['void']:.0%} | mkt {p['mkt_win']:.0%} model {mw} | EV {p['ev']:+.1%}")
