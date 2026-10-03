"""
Discover SportyBet (category, tournament) ids for whitelisted competitions.

WHY: price coverage, not market breadth, is what caps production. On
2026-09-17 only 8 of 22 verified fixtures carried ANY SportyBet price, so 14
could produce no acca leg of any kind -- an unpriced market is not bettable
(HR35). The cause is the id map: 37 of 77 registry competitions are bookable;
the other 40 have no SportyBet tournament id, so the cache rebuild skips them
and every fixture in them reaches the board as NO DATA - PENDING.

The Architect's target -- "if we have 100 fixtures verified, 100 fixtures is
going to be produced" -- needs those ids.

This script reads SportyBet's OWN menu API and reports what it finds. It does
not write the id map: a guessed tournament id produces confident WRONG data,
which is the exact failure that once filled Premier_League.json with
"Betis v Getafe". Matches are proposed here for review and pasted into
booking/rebuild_cache.SPORTYBET_CATEGORY_TOURNAMENT deliberately.

Usage:
    python scripts/discover_sportybet_ids.py
    python scripts/discover_sportybet_ids.py --all     # dump every menu entry
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

MENU_URLS = [
    "https://www.sportybet.com/api/ng/factsCenter/sportList",
    "https://www.sportybet.com/api/ng/factsCenter/popularAndSportList",
]

# The menu spans EVERY sport. Without this filter the matcher proposed
# Finland's "Liiga" (ICE HOCKEY) for the Estonian Meistriliiga and offered
# Slovak "Extraliga" (ice hockey) and "ECS Hungary T10 League" (cricket) as
# football candidates. A tournament id from the wrong sport is a wrong id, and
# a wrong id produces confident fabricated fixtures.
FOOTBALL_SPORT_IDS = {"sr:sport:1", "1"}
FOOTBALL_SPORT_NAMES = {"football", "soccer"}

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept": "application/json",
}


# Registry name -> the name SportyBet's football menu actually uses.
#
# These are genuine RENAMES or local-language names for the same top flight,
# not fuzzy guesses: each was read off the football-only menu under the
# league's own country. Explicit so the mapping is reviewable and the match is
# reproducible, rather than depending on a substring rule that once paired the
# Estonian Meistriliiga with Finnish ICE HOCKEY.
MENU_ALIAS: dict[str, str] = {
    "Romanian Liga I": "Superliga",              # renamed from Liga I in 2022
    "Ukrainian Premier League": "Premier League",
    "Serbian Super Liga": "Superliga",
    "Slovak Super Liga": "Superliga",
    "Bulgarian First League": "Parva Liga",      # Vtora Liga is the 2nd tier
    "Israeli Premier League": "Premier League",
    "Cypriot First Division": "1st Division",
    "Albanian Superliga": "Kategoria Superiore",
    "Armenian Premier League": "Premier League",
    "Azerbaijani Premyer Liqa": "Premier League",
    "Belarusian Premier League": "Vysshaya Liga",
    "Kazakhstan Premier League": "Premier League",
    "Lithuanian A Lyga": "TOPLYGA",              # A Lyga's current sponsor name
    "Maltese Premier League": "Premier League",
    "Estonian Meistriliiga": "Premium Liiga",    # Meistriliiga's official name
    "Georgian Erovnuli Liga": "Erovnuli Liga",
    "Finnish Veikkausliiga": "Veikkausliiga",
    "Hungarian NB I": "NB I",
    "Slovenian PrvaLiga": "PrvaLiga",
    "Latvian Virsliga": "Virsliga",
    # DELIBERATELY ABSENT: Montenegrin First League. The football menu lists
    # only "2. CFL" for Montenegro -- the SECOND division. Mapping the top
    # flight to it would file second-tier fixtures as first-tier.
}


def _norm(s: str) -> str:
    keep = "".join(c.lower() if (c.isalnum() or c.isspace()) else " " for c in (s or ""))
    return " ".join(keep.split())


def fetch_menu() -> list[dict]:
    """Every (category, tournament) the menu exposes. [] if unreachable."""
    import requests

    entries: list[dict] = []
    for url in MENU_URLS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            payload = r.json()
        except Exception as e:
            print(f"  ! {url.rsplit('/', 1)[-1]}: {type(e).__name__}: {str(e)[:90]}")
            continue

        data = payload.get("data") if isinstance(payload, dict) else payload
        if not data:
            continue

        # The menu nests sport -> categories -> tournaments. Shapes differ
        # slightly between the two endpoints, so walk defensively rather than
        # assuming one layout.
        def is_football(node: dict) -> bool:
            return (str(node.get("id") or "") in FOOTBALL_SPORT_IDS
                    or _norm(node.get("name") or "") in FOOTBALL_SPORT_NAMES)

        def walk(node, cat_id=None, cat_name=None):
            if isinstance(node, list):
                for x in node:
                    walk(x, cat_id, cat_name)
                return
            if not isinstance(node, dict):
                return
            if "categories" in node:
                # A node carrying categories is a SPORT. Descend only into
                # football; every other sport's tournaments are noise that
                # collides with football league names across countries.
                if not is_football(node):
                    return
                for c in node.get("categories") or []:
                    walk(c, c.get("id"), c.get("name"))
                return
            if "tournaments" in node:
                cid = node.get("id", cat_id)
                cname = node.get("name", cat_name)
                for t in node.get("tournaments") or []:
                    entries.append({
                        "category_id": cid, "category": cname,
                        "tournament_id": t.get("id"), "tournament": t.get("name"),
                    })
                return
            for v in node.values():
                if isinstance(v, (list, dict)):
                    walk(v, cat_id, cat_name)

        walk(data)
        if entries:
            break
    return entries


def _numeric(v):
    """SportyBet ids arrive as 'sr:category:4' / 'sr:tournament:17' or ints."""
    if isinstance(v, int):
        return v
    s = str(v or "")
    tail = s.rsplit(":", 1)[-1]
    return int(tail) if tail.isdigit() else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="dump every menu entry")
    args = ap.parse_args()

    reg_entries = json.loads(
        (REPO_ROOT / "config" / "leagues.json").read_text(encoding="utf-8"))["leagues"]
    registry = [e["name"] for e in reg_entries]
    country_of = {e["name"]: e.get("country") for e in reg_entries}

    # SportyBet's category name is the COUNTRY. A few differ from the registry's
    # spelling; map only the ones actually observed in the menu.
    country_alias = {
        "Republic of Ireland": {"ireland", "republic of ireland"},
        "Czech Republic": {"czech republic", "czechia"},
        "North Macedonia": {"north macedonia", "macedonia"},
        "Bosnia and Herzegovina": {"bosnia and herzegovina", "bosnia herzegovina"},
        "Turkey": {"turkey", "turkiye"},
        "Faroe Islands": {"faroe islands", "faroe island"},
        "Northern Ireland": {"northern ireland"},
        "England": {"england"}, "Scotland": {"scotland"}, "Wales": {"wales"},
    }

    def country_ok(league: str, category: str) -> bool:
        """The menu category must BE the league's country.

        Without this the name matcher happily proposed
            "Estonian Meistriliiga": (40, 134)   # Finland / Liiga
        because "liiga" is a substring of "meistriliiga". That is the same
        wrong-id failure that once filled Premier_League.json with
        "Betis v Getafe": a confident id pointing at another country's
        competition produces plausible, entirely fabricated fixtures.
        """
        want = country_of.get(league)
        if not want:
            return False
        got = _norm(category)
        allowed = country_alias.get(want, {_norm(want)})
        return got in {_norm(a) for a in allowed}

    try:
        from booking.rebuild_cache import SPORTYBET_CATEGORY_TOURNAMENT as IDS
    except Exception:
        IDS = {}

    # (0, 0) is a PLACEHOLDER meaning "no id resolved", not an id. Several
    # major leagues sit at (0,0) -- Austrian Bundesliga, Ekstraklasa,
    # Eliteserien, Greek Super League, HNL, Danish Superliga, Czech First
    # League -- so counting a present key as "has an id" overstated coverage
    # and hid exactly the leagues worth fixing.
    def _resolved(name: str) -> bool:
        v = IDS.get(name)
        return bool(v) and tuple(v)[:2] != (0, 0)

    missing = [l for l in registry if not _resolved(l)]
    print(f"Registry: {len(registry)} competitions · resolved id: "
          f"{len(registry) - len(missing)} · MISSING (incl. (0,0) placeholders): "
          f"{len(missing)}")
    print("Querying SportyBet's menu...")
    entries = fetch_menu()
    print(f"Menu returned {len(entries)} (category, tournament) entr(ies)\n")

    if not entries:
        print("NO MENU DATA — cannot propose any id. Reporting the gap rather "
              "than guessing (HR35).")
        return 1

    if args.all:
        for e in sorted(entries, key=lambda x: (str(x['category']), str(x['tournament']))):
            print(f"  {str(e['category'])[:24]:<24} {str(e['tournament'])[:38]:<38} "
                  f"({_numeric(e['category_id'])}, {_numeric(e['tournament_id'])})")
        return 0

    by_norm: dict[str, list[dict]] = {}
    for e in entries:
        by_norm.setdefault(_norm(e["tournament"]), []).append(e)

    proposed, unmatched = [], []
    for league in missing:
        n = _norm(MENU_ALIAS.get(league, league))
        hits = by_norm.get(n) or []
        if not hits:
            # Only accept a containment match when it is UNIQUE. Several
            # near-matches means ambiguity, and an ambiguous id is a wrong id.
            cands = [e for k, v in by_norm.items() if n and (n in k or k in n) for e in v]
            hits = cands if len(cands) == 1 else []
        # COUNTRY GUARD: a name match in the wrong country is a wrong id, not a
        # weak one. Applied before uniqueness so a cross-country hit is dropped
        # rather than being the single "unique" match that gets proposed.
        hits = [e for e in hits if country_ok(league, e.get("category") or "")]
        if len(hits) == 1:
            e = hits[0]
            cid, tid = _numeric(e["category_id"]), _numeric(e["tournament_id"])
            if cid and tid:
                proposed.append((league, e["category"], e["tournament"], cid, tid))
                continue
        unmatched.append(league)

    print(f"PROPOSED ({len(proposed)}) — review before pasting into "
          f"booking/rebuild_cache.SPORTYBET_CATEGORY_TOURNAMENT:\n")
    for league, cat, tour, cid, tid in proposed:
        print(f'    "{league}": ({cid}, {tid}),'.ljust(52)
              + f"# {cat} / {tour}")

    print(f"\nUNMATCHED ({len(unmatched)}) — SportyBet's menu does not list "
          f"these right now; they stay at no-id:")
    for l in unmatched:
        print(f"    {l}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
