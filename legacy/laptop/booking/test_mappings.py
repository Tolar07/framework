#!/usr/bin/env python3
"""Test SportyBet direct URLs to discover correct category/tournament mappings."""

import asyncio
import socket
from playwright.async_api import async_playwright

# Known working IPs for sportybet.com.ng
FALLBACK_IPS = ["104.21.10.148", "172.67.163.154"]

def _resolver_rule():
    host = "sportybet.com.ng"
    rules = []
    for ip in FALLBACK_IPS:
        rules.append(f"MAP {host}:443 {ip}")
    return ",".join(rules)

# Current mappings to test
MAPPINGS = {
    "Bundesliga": (7, 34),
    "Premier League": (32, 8),
    "La Liga": (31, 23),
    "Serie A": (30, 35),
    "Championship": (1, 17),
    "Ligue 1": (7, 35),
    "Ligue 2": (7, 36),
    "Primeira Liga": (32, 9),
    "Serie B": (30, 36),
    "La Liga 2": (31, 9),
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
            for i, row in enumerate(rows[:5]):
                home_el = await row.query_selector(".teams .home-team")
                away_el = await row.query_selector(".teams .away-team")
                if home_el and away_el:
                    home = (await home_el.inner_text()).strip()
                    away = (await away_el.inner_text()).strip()
                    if home and away:
                        teams.append(f"{home} v {away}")

            if teams:
                print(f"Sample teams: {teams[:3]}")

                # Check if teams look right for the league
                german_teams = ["Bayern", "Dortmund", "Leipzig", "Frankfurt", "Leverkusen", "Wolfsburg", "Union", "Freiburg", "Mainz", "Augsburg", "Bochum", "Heidenheim", "St. Pauli", "Holstein Kiel"]
                english_teams = ["Arsenal", "Liverpool", "City", "United", "Chelsea", "Tottenham", "Newcastle", "Brighton", "Aston Villa", "West Ham", "Crystal Palace", "Fulham", "Brentford", "Nottingham", "Everton", "Wolves", "Bournemouth", "Leicester", "Southampton", "Ipswich"]
                spanish_teams = ["Real Madrid", "Barcelona", "Atletico", "Athletic", "Villarreal", "Betis", "Real Sociedad", "Sevilla", "Valencia", "Girona", "Osasuna", "Celta", "Mallorca", "Rayo", "Getafe", "Las Palmas", "Alaves", "Espanyol", "Leganes", "Valladolid"]
                french_teams = ["PSG", "Monaco", "Marseille", "Lyon", "Lille", "Lens", "Nice", "Rennes", "Reims", "Montpellier", "Toulouse", "Brest", "Nantes", "Strasbourg", "Auxerre", "Angers", "Le Havre", "St Etienne"]
                italian_teams = ["Inter", "Juventus", "Milan", "Napoli", "Roma", "Lazio", "Atalanta", "Fiorentina", "Bologna", "Torino", "Genoa", "Como", "Cagliari", "Lecce", "Parma", "Udinese", "Verona", "Empoli", "Venezia", "Monza"]
                portuguese_teams = ["Porto", "Benfica", "Sporting", "Braga", "Vitoria", "Guimaraes", "Famalicao", "Casa Pia", "Estoril", "Moreirense", "Gil Vicente", "Santa Clara", "Arouca", "Rio Ave", "Farense", "Boavista", "Estrela", "Nacional", "AVS"]

                all_teams = " ".join(teams)

                # Score against known league teams
                scores = {
                    "Bundesliga": sum(1 for t in german_teams if t.lower() in all_teams.lower()),
                    "Premier League": sum(1 for t in english_teams if t.lower() in all_teams.lower()),
                    "La Liga": sum(1 for t in spanish_teams if t.lower() in all_teams.lower()),
                    "Serie A": sum(1 for t in italian_teams if t.lower() in all_teams.lower()),
                    "Championship": 0,  # Will check separately
                    "Ligue 1": sum(1 for t in french_teams if t.lower() in all_teams.lower()),
                    "Ligue 2": sum(1 for t in french_teams if t.lower() in all_teams.lower()),
                    "Primeira Liga": sum(1 for t in portuguese_teams if t.lower() in all_teams.lower()),
                    "Serie B": sum(1 for t in italian_teams if t.lower() in all_teams.lower()),
                    "La Liga 2": sum(1 for t in spanish_teams if t.lower() in all_teams.lower()),
                }

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

        results = []
        for league, (cat_id, tour_id) in MAPPINGS.items():
            result = await test_league(page, league, cat_id, tour_id)
            results.append(result)

        await browser.close()

        print("\n\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        for r in results:
            if r.get("works"):
                print(f"OK {r['league']}: cat={r['cat_id']}, tour={r['tour_id']} -> {r['best_match']} ({r['match_scores'].get(r['best_match'], 0)} matches)")
            else:
                print(f"✗ {r['league']}: FAILED - {r.get('reason', 'unknown')}")

        # Save results
        import json
        with open("mapping_results.json", "w") as f:
            json.dump(results, f, indent=2)
        print("\nResults saved to mapping_results.json")

if __name__ == "__main__":
    asyncio.run(main())