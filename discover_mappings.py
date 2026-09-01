#!/usr/bin/env python3
"""Systematic discovery of correct SportyBet category/tournament IDs for all acca leagues."""

import asyncio
from playwright.async_api import async_playwright

# Known working IPs for sportybet.com.ng
FALLBACK_IPS = ["104.21.10.148", "172.67.163.154"]

def _resolver_rule():
    host = "sportybet.com.ng"
    rules = []
    for ip in FALLBACK_IPS:
        rules.append(f"MAP {host}:443 {ip}")
    return ",".join(rules)

# Leagues from acca_2026-08-29.json that need correct mappings
ACCA_LEAGUES = [
    "Premier League",
    "Championship",
    "Serie A",
    "Serie B",
    "Bundesliga",
    "Ligue 1",
    "Ligue 2",
    "La Liga",
    "La Liga 2",
    "Primeira Liga",
    "Turkish Super Lig",
    "Russian Premier League",
    "Swiss Super League",
    "Belgian Pro League",
    "Scottish Premiership",
]

# Current mappings (all wrong)
CURRENT_MAPPINGS = {
    "Premier League": (32, 8),
    "Championship": (1, 17),
    "Serie A": (30, 35),
    "Serie B": (30, 36),
    "Bundesliga": (7, 34),
    "Ligue 1": (7, 35),
    "Ligue 2": (7, 36),
    "La Liga": (31, 23),
    "La Liga 2": (31, 9),
    "Primeira Liga": (32, 9),
    "Turkish Super Lig": (0, 0),
    "Russian Premier League": (0, 0),
    "Swiss Super League": (0, 0),
    "Belgian Pro League": (0, 0),
    "Scottish Premiership": (0, 0),
}

# Known team names to validate correct league
LEAGUE_TEAMS = {
    "Premier League": ["Arsenal", "Liverpool", "Manchester City", "Chelsea", "Tottenham", "Newcastle", "Aston Villa", "West Ham", "Brighton", "Crystal Palace", "Fulham", "Brentford", "Nottingham", "Everton", "Wolves", "Bournemouth", "Leicester", "Southampton", "Ipswich"],
    "Championship": ["Leeds", "Sheffield", "Sunderland", "Middlesbrough", "Norwich", "Watford", "West Brom", "Coventry", "Preston", "Cardiff", "Swansea", "Bristol City", "Hull", "QPR", "Blackburn", "Millwall", "Plymouth", "Stoke", "Oxford", "Derby"],
    "Serie A": ["Inter", "Juventus", "Milan", "Napoli", "Roma", "Lazio", "Atalanta", "Fiorentina", "Bologna", "Torino", "Genoa", "Como", "Cagliari", "Lecce", "Parma", "Udinese", "Verona", "Empoli", "Venezia", "Monza"],
    "Serie B": ["Cremonese", "Catanzaro", "Palermo", "Sampdoria", "Brescia", "Reggiana", "Cittadella", "Pisa", "Spezia", "Modena", "Bari", "Cosenza", "Frosinone", "Mantova", "Carrarese", "Juve Stabia", "Sassuolo", "Cesena", "Virtus Entella", "Salernitana"],
    "Bundesliga": ["Bayern", "Dortmund", "Leipzig", "Frankfurt", "Leverkusen", "Wolfsburg", "Union", "Freiburg", "Mainz", "Augsburg", "Bochum", "Heidenheim", "St. Pauli", "Holstein Kiel", "Werder Bremen", "Hoffenheim", "Gladbach", "Darmstadt"],
    "Ligue 1": ["PSG", "Monaco", "Marseille", "Lyon", "Lille", "Lens", "Nice", "Rennes", "Reims", "Montpellier", "Toulouse", "Brest", "Nantes", "Strasbourg", "Auxerre", "Angers", "Le Havre", "St Etienne"],
    "Ligue 2": ["Metz", "Bordeaux", "Paris FC", "Rodez", "Annecy", "Amiens", "Bastia", "Caen", "Guingamp", "Laval", "Martigues", "Pau", "Troyes", "Dunkerque", "Grenoble", "Ajaccio", "Clermont", "Lorient"],
    "La Liga": ["Real Madrid", "Barcelona", "Atletico", "Athletic", "Villarreal", "Betis", "Real Sociedad", "Sevilla", "Valencia", "Girona", "Osasuna", "Celta", "Mallorca", "Rayo", "Getafe", "Las Palmas", "Alaves", "Espanyol", "Leganes", "Valladolid"],
    "La Liga 2": ["Levante", "Oviedo", "Almeria", "Granada", "Racing", "Elche", "Albacete", "Eibar", "Tenerife", "Zaragoza", "Huesca", "Mirandes", "Eldense", "Burgos", "Cordoba", "Malaga", "Deportivo", "Cartagena", "Castellon", "Alcorcon"],
    "Primeira Liga": ["Porto", "Benfica", "Sporting", "Braga", "Vitoria", "Guimaraes", "Famalicao", "Casa Pia", "Estoril", "Moreirense", "Gil Vicente", "Santa Clara", "Arouca", "Rio Ave", "Farense", "Boavista", "Estrela", "Nacional", "AVS"],
    "Turkish Super Lig": ["Galatasaray", "Fenerbahce", "Besiktas", "Trabzonspor", "Basaksehir", "Kasimpasa", "Adana Demirspor", "Alanyaspor", "Antalyaspor", "Gaziantep", "Hatayspor", "Kayserispor", "Konyaspor", "Rizespor", "Samsunspor", "Sivasspor", "Bodrum", "Eyupspor", "Goztepe", "Kocaelispor"],
    "Russian Premier League": ["Zenit", "Spartak", "CSKA", "Dynamo", "Lokomotiv", "Krasnodar", "Rostov", "Akhmat", "Khimki", "Krylia Sovetov", "Orenburg", "Pari NN", "Rubin", "Sochi", "Ural", "Ufa", "Fakel", "Baltika"],
    "Swiss Super League": ["Young Boys", "Basel", "Zurich", "Servette", "Lugano", "St. Gallen", "Luzern", "Sion", "Winterthur", "Yverdon", "GC", "Lausanne"],
    "Belgian Pro League": ["Anderlecht", "Club Brugge", "Union SG", "Antwerp", "Genk", "Gent", "Cercle Brugge", "Standard", "Charleroi", "Mechelen", "OH Leuven", "Westerlo", "Kortrijk", "St. Truiden", "Eupen", "Dender"],
    "Scottish Premiership": ["Celtic", "Rangers", "Hearts", "Hibs", "Aberdeen", "St. Mirren", "Motherwell", "Dundee", "Kilmarnock", "St. Johnstone", "Ross County", "Falkirk"],
}

async def test_league(page, league, cat_id, tour_id):
    host = "sportybet.com.ng"
    direct_url = f"https://{host}/ng/sport/football/sr:category:{cat_id}/sr:tournament:{tour_id}?source=sport_menu&sort=2"

    print(f"\n{'='*60}")
    print(f"Testing: {league}")
    print(f"URL: {direct_url}")
    print(f"IDs: category={cat_id}, tournament={tour_id}")

    try:
        await page.goto(direct_url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(5000)

        # Check for fixture rows
        rows = await page.query_selector_all(".m-table-row.match-row")
        print(f"Fixture rows found: {len(rows)}")

        if rows:
            # Extract first few team names to verify
            teams = []
            for i, row in enumerate(rows[:10]):
                home_el = await row.query_selector(".teams .home-team")
                away_el = await row.query_selector(".teams .away-team")
                if home_el and away_el:
                    home = (await home_el.inner_text()).strip()
                    away = (await away_el.inner_text()).strip()
                    if home and away:
                        teams.append(f"{home} v {away}")

            if teams:
                print(f"Sample teams: {teams[:5]}")

                # Score against known league teams
                expected_teams = LEAGUE_TEAMS.get(league, [])
                all_teams = " ".join(teams)

                scores = {}
                for l, t_list in LEAGUE_TEAMS.items():
                    scores[l] = sum(1 for t in t_list if t.lower() in all_teams.lower())

                print(f"Match scores: {scores}")
                best_match = max(scores, key=scores.get)
                print(f"Best match: {best_match} (score: {scores[best_match]})")

                return {
                    "league": league,
                    "cat_id": cat_id,
                    "tour_id": tour_id,
                    "works": True,
                    "sample_teams": teams[:5],
                    "match_scores": scores,
                    "best_match": best_match
                }
            else:
                print("Rows found but no team names extracted")
                return {"league": league, "cat_id": cat_id, "tour_id": tour_id, "works": False, "reason": "no team names"}
        else:
            print("No fixture rows found")
            return {"league": league, "cat_id": cat_id, "tour_id": tour_id, "works": False, "reason": "no rows"}

    except Exception as e:
        print(f"Error: {e}")
        return {"league": league, "cat_id": cat_id, "tour_id": tour_id, "works": False, "reason": str(e)[:100]}

async def test_category_tournament_combinations(page, league, cat_range=range(1, 50), tour_range=range(1, 50)):
    """Test multiple category/tournament combinations to find working one."""
    print(f"\n{'#'*60}")
    print(f"# DISCOVERING MAPPING FOR: {league}")
    print(f"{'#'*60}")

    best_result = None
    best_score = 0

    for cat_id in cat_range:
        for tour_id in tour_range:
            # Skip current (wrong) mappings
            if (cat_id, tour_id) == CURRENT_MAPPINGS.get(league, (0, 0)):
                continue

            result = await test_league(page, league, cat_id, tour_id)
            if result.get("works"):
                score = result["match_scores"].get(result["best_match"], 0)
                if score > best_score:
                    best_score = score
                    best_result = result
                    if score >= 3:  # Good match found
                        print(f"  *** GOOD MATCH FOUND: {league} -> cat={cat_id}, tour={tour_id} (score: {score}) ***")

    return best_result

async def main():
    resolver_rule = _resolver_rule()
    launch_args = ["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"]
    if resolver_rule:
        launch_args.append(f"--host-resolver-rules={resolver_rule}")
    print(f"Launch args: {launch_args}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=launch_args)
        ctx = await browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()

        results = {}
        for league in ACCA_LEAGUES:
            if CURRENT_MAPPINGS.get(league, (0, 0)) != (0, 0):
                # Test current mapping first
                cat_id, tour_id = CURRENT_MAPPINGS[league]
                result = await test_league(page, league, cat_id, tour_id)
                if result.get("works") and result["match_scores"].get(result["best_match"], 0) >= 2:
                    results[league] = result
                else:
                    # Try to discover correct mapping
                    best = await test_category_tournament_combinations(page, league)
                    if best:
                        results[league] = best
            else:
                # No current mapping, try to discover
                best = await test_category_tournament_combinations(page, league)
                if best:
                    results[league] = best

        await browser.close()

        print("\n\n" + "="*60)
        print("FINAL RESULTS")
        print("="*60)
        for league, r in results.items():
            if r.get("works"):
                print(f"OK {league}: cat={r['cat_id']}, tour={r['tour_id']} -> {r['best_match']} ({r['match_scores'].get(r['best_match'], 0)} matches)")
            else:
                print(f"✗ {league}: FAILED - {r.get('reason', 'unknown')}")

        # Save results
        import json
        with open("discovered_mappings.json", "w") as f:
            json.dump(results, f, indent=2)
        print("\nResults saved to discovered_mappings.json")

if __name__ == "__main__":
    asyncio.run(main())