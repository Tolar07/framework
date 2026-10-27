"""
Where each pick is played — country + league, so it can be found on the
betting site (standing order 28, Architect 2026-10-04).

Club competitions read "country · league" (Spain · La Liga 2), the order the
betting apps are browsed in: country, then league, then match. National-team
and continental competitions have no single country, so they read as the
competition alone (UEFA Nations League).

Names follow what SportyBet shows where the code has it verified (La Liga 2 is
"LALIGA HYPERMOTION", Primeira Liga is "Liga Portugal" — see
pipeline/odds_sportybet.py). A league missing from this table shows its own
name and no country: a guessed country is worse than none (HR35).
"""
from __future__ import annotations

# Framework league -> (country, league as shown). Country None = no single
# country (national teams, continental club cups).
COMPETITIONS: dict[str, tuple[str | None, str]] = {
    "Premier League": ("England", "Premier League"),
    "Championship": ("England", "Championship"),
    "League One": ("England", "League One"),
    "League Two": ("England", "League Two"),
    "National League": ("England", "National League"),
    "FA Cup": ("England", "FA Cup"),
    "La Liga": ("Spain", "La Liga"),
    "La Liga 2": ("Spain", "La Liga 2 / Hypermotion"),
    "Serie A": ("Italy", "Serie A"),
    "Serie B": ("Italy", "Serie B"),
    "Bundesliga": ("Germany", "Bundesliga"),
    "2. Bundesliga": ("Germany", "2. Bundesliga"),
    "Ligue 1": ("France", "Ligue 1"),
    "Ligue 2": ("France", "Ligue 2"),
    "Primeira Liga": ("Portugal", "Primeira Liga / Liga Portugal"),
    "Eredivisie": ("Netherlands", "Eredivisie"),
    "Belgian Pro League": ("Belgium", "Pro League"),
    "Scottish Premiership": ("Scotland", "Premiership"),
    "Danish Superliga": ("Denmark", "Superliga"),
    "Ekstraklasa": ("Poland", "Ekstraklasa"),
    "HNL": ("Croatia", "HNL"),
    "Turkish Super Lig": ("Turkey", "Super Lig"),
    "Turkish Cup": ("Turkey", "Turkish Cup"),
    "Greek Super League": ("Greece", "Super League"),
    "Austrian Bundesliga": ("Austria", "Bundesliga"),
    "Swiss Super League": ("Switzerland", "Super League"),
    "Eliteserien": ("Norway", "Eliteserien"),
    "Allsvenskan": ("Sweden", "Allsvenskan"),
    "Champions League": (None, "UEFA Champions League"),
    "Europa League": (None, "UEFA Europa League"),
    "Conference League": (None, "UEFA Conference League"),
    "UEFA Nations League": (None, "UEFA Nations League"),
}

_ENGLAND = "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F"
_SCOTLAND = "\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F"


def _flag_of(iso2: str) -> str:
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso2)


FLAGS: dict[str, str] = {
    "England": _ENGLAND, "Scotland": _SCOTLAND,
    "Spain": _flag_of("ES"), "Italy": _flag_of("IT"), "Germany": _flag_of("DE"),
    "France": _flag_of("FR"), "Portugal": _flag_of("PT"),
    "Netherlands": _flag_of("NL"), "Belgium": _flag_of("BE"),
    "Denmark": _flag_of("DK"), "Poland": _flag_of("PL"), "Croatia": _flag_of("HR"),
    "Turkey": _flag_of("TR"), "Greece": _flag_of("GR"), "Austria": _flag_of("AT"),
    "Switzerland": _flag_of("CH"), "Norway": _flag_of("NO"), "Sweden": _flag_of("SE"),
}
TROPHY = "\U0001F3C6"


def league_of(fixture: str) -> str | None:
    """'Home v Away (League)' -> 'League'; None when no league is attached."""
    if not fixture.endswith(")") or " (" not in fixture:
        return None
    return fixture.rsplit(" (", 1)[1][:-1].strip() or None


def label(league: str | None, flag: bool = False) -> str:
    """'Spain · La Liga 2' for a club league, 'UEFA Nations League' for one with
    no single country. flag=True prefixes the country's flag (🏆 when there is
    no country) — for plain lines; fixed-width tables leave it off, because a
    flag's width breaks the column alignment."""
    if not league:
        return "PENDING"
    country, name = COMPETITIONS.get(league, (None, league))
    text = f"{country} · {name}" if country else name
    if not flag:
        return text
    mark = FLAGS.get(country, TROPHY) if country else TROPHY
    return f"{mark} {text}"


def where(fixture: str, league: str | None = None) -> str:
    """'Home v Away (🇪🇸 Spain · La Liga 2)' — a match plus where to find it.
    `fixture` may be the full 'Home v Away (League)' or the short 'Home v Away'
    with `league` given separately; with no league known the match is returned
    unchanged rather than with an invented one."""
    lg = league or league_of(fixture)
    short = fixture.rsplit(" (", 1)[0] if league_of(fixture) else fixture
    return f"{short} ({label(lg, flag=True)})" if lg else short
