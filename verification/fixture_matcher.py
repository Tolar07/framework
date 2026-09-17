"""
Cross-source fixture matching for OLP XDV ID403 verification.

Root cause this addresses (2026-09-06 diagnostic): FlashScore found 183
fixtures, BBC Sport found 132, but only 18 of 81 post-filter fixtures came
back VERIFIED (>=2 sources). With that much source volume on both sides,
an 18/81 verified rate points at a matching failure, not a data-availability
failure -- most likely team-name string mismatches ("Man Utd" vs
"Manchester United") or kickoff-time formatting differences preventing
otherwise-identical fixtures from being recognised as the same fixture.

This module does NOT change what counts as verified -- >=2 independent
sources per ID403 stays exactly as it is, untouched. It only makes the
matching that decides "are these the same fixture" more accurate, so
fixtures that ARE independently confirmed actually get recognised as such.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time
from typing import Optional


# Known alias collisions across FlashScore / BBC / SportyBet / API-Football.
# This is a STARTING POINT based on common naming conventions -- it is NOT
# complete. Log every unmatched-but-should-match pair you find in real runs
# and add it here. Treat this as a living file, not a one-time fix.
TEAM_ALIASES = {
    "man utd": "manchester united",
    "man united": "manchester united",
    "man city": "manchester city",
    "newcastle": "newcastle united",
    "brighton": "brighton & hove albion",
    "leeds": "leeds united",
    "west ham": "west ham united",
    "wolves": "wolverhampton wanderers",
    "spurs": "tottenham hotspur",
    "arsenal": "arsenal",
    "chelsea": "chelsea",
    "liverpool": "liverpool",
    "everton": "everton",
    "tottenham": "tottenham hotspur",
    "man city": "manchester city",
    "newcastle utd": "newcastle united",
    "brighton & hove": "brighton & hove albion",
    "leeds utd": "leeds united",
    "west ham utd": "west ham united",
    "wolverhampton wanderers": "wolverhampton wanderers",
    "tottenham hotspur": "tottenham hotspur",
    "aston villa": "aston villa",
    "aston villa fc": "aston villa",
    "brentford": "brentford",
    "fulham": "fulham",
    "crystal palace": "crystal palace",
    "southampton": "southampton",
    "ipswich": "ipswich town",
    "ipswich town": "ipswich town",
    "leicester": "leicester city",
    "leicester city": "leicester city",
    "nott'm forest": "nottingham forest",
    "nottm forest": "nottingham forest",
    "nottingham forest": "nottingham forest",
    "psg": "paris saint-germain",
    "paris saint-germain": "paris saint-germain",
    "inter": "inter milan",
    "inter milan": "inter milan",
    "ac milan": "ac milan",
    "juventus": "juventus",
    "roma": "roma",
    "napoli": "napoli",
    "lazio": "lazio",
    "atalanta": "atalanta",
    "marseille": "marseille",
    "psg": "paris saint-germain",
    "lyon": "lyon",
    "monaco": "monaco",
    "real madrid": "real madrid",
    "barcelona": "barcelona",
    "atletico madrid": "atletico madrid",
    "sevilla": "sevilla",
    "valencia": "valencia",
    "villarreal": "villarreal",
    "getafe": "getafe",
    "celta vigo": "celta vigo",
    "elche": "elche",
    "real sociedad": "real sociedad",
    "betis": "real betis",
    "real betis": "real betis",
    "osasuna": "osasuna",
    "alaves": "deportivo alaves",
    "deportivo alaves": "deportivo alaves",
    "celta": "celta vigo",
    "sociedad": "real sociedad",
    "estoril": "estoril",
    "arouca": "arouca",
    "benfica": "benfica",
    "porto": "fc porto",
    "sporting": "sporting lisbon",
    "sporting lisbon": "sporting lisbon",
    "braga": "sc braga",
    "guimaraes": "vitoria guimaraes",
    "nazare": "nazareno",
    "chertsey": "chertsey town",
    "carshalton": "carshalton athletic",
    "malvern town": "malvern town",
    "swindon s": "swindon supermarine",
    "winslow united": "winslow united",
    "sabadell": "ce sabadell",
    "cordoba": "cordoba cf",
    "nantes": "fc nantes",
    "nancy": "as nancy lorraine",
    "gaziantep fk": "gaziantep fk",
    "gaziatepe": "gaziatepe",
    "rizespor": "rizespor",
    "alanyaspor": "alanyaspor",
    "fc midtjylland": "fc midtjylland",
    "fc nordsjaelland": "fc nordsjaelland",
    "wieczysta krak�w": "wieczysta krakow",
    "zaglebie lubin": "zaglebie lubin",
    "pogon szczecin": "pogon szczecin",
    "wisla plock": "wisla plock",
    # --- Added 2026-09-16 -------------------------------------------------
    # Genuine synonyms: clubs where two sources use different NAMES, not just
    # different abbreviations, so no amount of normalisation reconciles them.
    # Each pair below was observed splitting a real fixture across two
    # single-source records on 2026-09-16.
    "rennes": "stade rennais",
    "stade rennais fc": "stade rennais",
    "deportivo": "deportivo la coruna",          # ESPN "Deportivo"
    "a coruna": "deportivo la coruna",           # FlashScore "A Coruna"
    "deportivo de la coruna": "deportivo la coruna",
    "krylia sovetov": "krylia sovetov samara",   # ESPN
    "samara": "krylia sovetov samara",           # FlashScore
    "athletic club": "athletic bilbao",          # ESPN
    "ath bilbao": "athletic bilbao",             # FlashScore "Ath. Bilbao"
    # "Athletic Club" loses its "club" token to _SUFFIX_PATTERN and arrives
    # here as bare "athletic", so the bare form needs the alias too. Safe
    # despite looking generic: "Atletico" folds to a different token, and a
    # fixture only merges when BOTH teams and the league also agree.
    "athletic": "athletic bilbao",
    "hapoel be er": "hapoel beer sheva",         # ESPN truncates "Be'er"
    "hapoel be er sheva": "hapoel beer sheva",
    "beer sheva": "hapoel beer sheva",
    "h beer sheva": "hapoel beer sheva",         # FlashScore "H. Beer Sheva"
    "omonia nicosia": "omonia",
    "olympiacos piraeus": "olympiacos",
    # Observed splitting the 2026-09-17 Europa League slate into 11 records for
    # 9 fixtures. Neither pair is reachable by normalisation: "RB" is an
    # initialism of "Red Bull", and "SG" of "Saint-Gilloise", so the short form
    # shares no token with the long one.
    # "Ferencvarosi" and "Ferencvaros" are different stems, not a prefix
    # relationship, so no token rule reconciles them.
    "ferencvarosi budapest": "ferencvaros",
    "ferencvarosi": "ferencvaros",
    "ferencvarosi tc": "ferencvaros",
    "rb salzburg": "red bull salzburg",
    "salzburg": "red bull salzburg",
    "union sg": "union saint gilloise",
    "union st gilloise": "union saint gilloise",
    "royale union sg": "union saint gilloise",
    # --- football-data.co.uk roster names -------------------------------
    # The Dixon-Coles fits are built from football-data's abbreviations, so
    # these map the fitted roster onto the same canonical form the fixture
    # sources normalise to. Without them a club is rated in the model but
    # unreachable from the board, and the fixture renders NO DATA - PENDING.
    "ath madrid": "atletico madrid",
    "club atletico de madrid": "atletico madrid",
    "ath bilbao": "athletic bilbao",
    "celta": "celta vigo",
    "rc celta de vigo": "celta vigo",
    "rc deportivo la coruna": "deportivo la coruna",
    "la coruna": "deportivo la coruna",
    "espanol": "espanyol",
    "rcd espanyol de barcelona": "espanyol",
    # After club-type stripping this arrives as "espanyol de barcelona", whose
    # token set contains "barcelona" -- so the subset rule matched BOTH Espanyol
    # and Barcelona in the roster, went ambiguous, and correctly refused to
    # guess. An explicit alias resolves it without loosening that rule.
    "espanyol de barcelona": "espanyol",
    "deportivo alaves": "alaves",
    "ca osasuna": "osasuna",
    "real betis": "betis",
    # --- Russian transliteration variants ---------------------------------
    # Sources romanise Cyrillic differently and the results are different
    # TOKENS, not prefixes, so no normalisation rule reconciles them. On
    # 2026-09-17 "Akron Togliatti" and "Akron Tolyatti" survived as two
    # separate fixtures against the same opponent, both carrying an identical
    # 51% pick -- one match counted twice on the board.
    "akron togliatti": "akron",
    "akron tolyatti": "akron",
    "togliatti": "akron",
    "tolyatti": "akron",
    "akhmat grozny": "akhmat",
    "gazovik orenburg": "orenburg",
    "dynamo makhachkala": "dinamo makhachkala",
    "dinamo moscow": "dynamo moscow",
    "krylya sovetov": "krylia sovetov samara",
    "sp moscow": "spartak moscow",
    "lok moscow": "lokomotiv moscow",
    "lokomotiv": "lokomotiv moscow",
    "zenit st petersburg": "zenit saint petersburg",
    "zenit": "zenit saint petersburg",
    "spartak moscow": "spartak moscow",
}

# Club-type tokens that carry no identifying information. Sources disagree on
# these constantly: ESPN says "NK Celje"/"SK Sturm Graz"/"AZ Alkmaar"/"FC
# Baltika Kaliningrad" where FlashScore says "Celje"/"Sturm Graz"/"Alkmaar"/
# "Baltika". Stripping them is what lets those pair up.
_SUFFIX_PATTERN = re.compile(
    r"\b(fc|cf|sc|afc|ac|as|ss|ssc|sv|sk|nk|hk|bk|ik|if|az|ogc|rc|rcd|cd|ud|sd|ca|fk|ff|vfl|vfb|"
    r"club|calcio|de futebol|voetbalclub)\b",
    re.IGNORECASE,
)

# Whole-token abbreviation expansions. Applied per token, never as substrings,
# so "utd" -> "united" cannot corrupt a club whose name merely contains those
# letters. Only unambiguous football abbreviations belong here.
_TOKEN_EXPANSIONS = {
    "utd": "united",
    "sheff": "sheffield",
    "atl": "atletico",
    # "ath" is deliberately NOT expanded. In football-data naming it is
    # ambiguous: "Ath Madrid" is Atletico Madrid while "Ath Bilbao" is Athletic
    # Bilbao, so a blanket ath->athletic would silently rewrite Atletico into
    # Athletic. Both forms are handled by explicit aliases below instead.
    "din": "dinamo",
    "dyn": "dinamo",
    "lok": "lokomotiv",
    "loko": "lokomotiv",
    "sp": "spartak",
    "st": "saint",
    "m": "monchengladbach",
    "mgladbach": "monchengladbach",
    "gladbach": "monchengladbach",
    "h": "hapoel",
    "utrecht": "utrecht",
}

# Accent/diacritic folding: ESPN emits "Atlético Madrid", FlashScore "Atl.
# Madrid"; without folding these never meet even after expansion.
_ACCENTS = str.maketrans(
    "áàâäãåéèêëíìîïóòôöõúùûüýÿñçšžđø",
    "aaaaaaeeeeiiiiooooouuuuyyncszdo",
)

_PUNCT_PATTERN = re.compile(r"[^\w\s]")
_WHITESPACE_PATTERN = re.compile(r"\s+")

# Tokens too generic to identify a club on their own. A token-subset match is
# only allowed when the shorter name contributes something outside this set,
# so "Real Madrid" can never collapse into "Real Sociedad" via "real".
_GENERIC_TOKENS = {
    "united", "city", "town", "rovers", "wanderers", "albion", "county",
    "real", "royal", "athletic", "atletico", "sporting", "racing", "national",
    "saint", "de", "la", "le", "los", "the", "1", "04", "05", "07", "1899",
}


def normalize_team_name(name: str) -> str:
    """Lowercase, fold accents, strip club-type noise, expand abbreviations,
    then apply the alias table. Comparison-only -- never used for display,
    since HR53 requires full club names in output."""
    n = name.strip().lower().translate(_ACCENTS)
    n = _PUNCT_PATTERN.sub(" ", n)
    n = _SUFFIX_PATTERN.sub(" ", n)
    n = _WHITESPACE_PATTERN.sub(" ", n).strip()
    # Alias the raw-normalised form first: entries like "man utd" are written
    # pre-expansion, so this has to run before token expansion.
    n = TEAM_ALIASES.get(n, n)
    n = " ".join(_TOKEN_EXPANSIONS.get(t, t) for t in n.split())
    n = _WHITESPACE_PATTERN.sub(" ", n).strip()
    # And again after expansion, so aliases can be written either way round.
    return TEAM_ALIASES.get(n, n)


def _tokens(normalized: str) -> frozenset:
    return frozenset(normalized.split())


def names_match(a: str, b: str) -> bool:
    """True when two already-normalised names denote the same club.

    Exact equality, or one name's tokens being a subset of the other's. The
    subset rule is what reconciles the very common case where one source
    qualifies a club with its city and another does not -- "Olympiacos" vs
    "Olympiacos Piraeus", "Jagiellonia" vs "Jagiellonia Bialystok", "Zenit" vs
    "Zenit St Petersburg", "Leverkusen" vs "Bayer Leverkusen".

    It is deliberately constrained: the shorter name must contribute at least
    one non-generic token, so pairs that merely share a common word ("Real
    Madrid"/"Real Sociedad", "Manchester United"/"Manchester City") never
    collapse. Callers additionally require BOTH teams, the league and the
    kickoff to agree before treating two records as one fixture, so a single
    loose team comparison cannot by itself merge distinct fixtures.
    """
    if a == b:
        return True
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    smaller, larger = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if not smaller < larger:
        return False
    return any(t not in _GENERIC_TOKENS and len(t) >= 4 for t in smaller)


def _parse_kickoff(value: str) -> Optional[datetime]:
    """Accepts ISO 8601 with or without a timezone offset. Naive datetimes
    are assumed UTC -- if a specific source is confirmed to report local
    time instead, that source needs its own conversion BEFORE it reaches
    this matcher. Never guess a timezone here."""
    if not value:
        return None
    v = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        try:
            dt = datetime.fromisoformat(v[:10])
        except ValueError:
            # Try to parse as time-only (HH:MM or HH:MM:SS) and assume today's date
            try:
                # Split by ':' and check if we have 2 or 3 parts
                parts = v.split(':')
                if len(parts) in (2, 3):
                    # Ensure each part is digits and within range
                    if all(part.isdigit() for part in parts):
                        h = int(parts[0])
                        m = int(parts[1]) if len(parts) >= 2 else 0
                        s = int(parts[2]) if len(parts) == 3 else 0
                        if 0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59:
                            today = datetime.now().date()
                            dt = datetime.combine(today, time(h, m, s))
                        else:
                            return None
                    else:
                        return None
                else:
                    return None
            except Exception:
                return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(tz=None).replace(tzinfo=None)
    return dt


def normalize_kickoff(value: str) -> Optional[str]:
    """Normalize a kickoff string to the format 'YYYY-MM-DDTHH:MM:SS' (without timezone) or None if invalid."""
    dt = _parse_kickoff(value)
    if dt is None:
        return None
    return dt.isoformat()


@dataclass
class SourceFixture:
    """Minimal shape a source adapter must produce. Adapt your existing
    FlashScore/BBC/SportyBet fixture objects into this before calling
    match_fixtures -- this module doesn't know or care how you fetched them."""
    home: str
    away: str
    league: str
    kickoff_utc: str  # raw string as returned by the source
    raw: dict = field(default_factory=dict)


class VerificationTier:
    """Mirrors the ID403.1 tier names this matcher is actually capable of
    producing. NO_DATA and DERIVED are NOT produced here -- those are
    upstream/downstream concepts (a fixture this matcher never saw at all,
    or an engine-derived value) and stay out of this module's vocabulary
    on purpose, so it never claims a tier it can't actually determine."""
    VERIFIED = "VERIFIED"
    SINGLE_SOURCE = "SINGLE-SOURCE"
    CONFLICT = "CONFLICT"


@dataclass
class MatchedFixture:
    home: str
    away: str
    league: str
    kickoff_utc: Optional[datetime]  # representative kickoff; None when CONFLICT
    sources: dict = field(default_factory=dict)  # source_name -> SourceFixture
    tier: str = VerificationTier.SINGLE_SOURCE
    conflict_detail: Optional[list] = None  # populated only when tier == CONFLICT

    @property
    def source_count(self) -> int:
        return len(self.sources)

    @property
    def is_verified(self) -> bool:
        # ID403: >=2 INDEPENDENT sources -- but a CONFLICT is explicitly
        # NOT verified even with 2+ sources, since they disagree. Silently
        # counting a conflicting pair as "verified" would be worse than
        # under-verifying: it would give false confidence to a fixture
        # whose actual kickoff time is in dispute between sources.
        return self.tier == VerificationTier.VERIFIED


def match_fixtures(
    fixture_lists: dict,  # {"flashscore": [SourceFixture, ...], "bbc": [...], ...}
    kickoff_tolerance: timedelta = timedelta(minutes=90),
) -> list:
    """
    Merge fixture lists from multiple sources into consolidated
    MatchedFixture records, matching on (normalized home, normalized away,
    league) first, then clustering by kickoff time within tolerance.

    kickoff_tolerance defaults to 90 minutes because sources disagree on
    kickoff time far more often than they disagree on which teams are
    playing (TV rescheduling, "confirmed" vs "provisional" times, timezone
    bugs).

    ID403.1 CONFLICT handling: if sources agree on (home, away, league) but
    their kickoff times fall into more than one cluster beyond tolerance,
    that is a genuine disagreement -- not two different fixtures that
    happen to share team names. Those are tagged CONFLICT with full detail
    on which source said what, rather than silently splitting into two
    separate single-source entries (which would hide the disagreement).
    """
    buckets: dict = {}
    for source_name, fixtures in fixture_lists.items():
        for fx in fixtures:
            h = normalize_team_name(fx.home)
            a = normalize_team_name(fx.away)
            league_key = (fx.league or "").strip().lower()
            kickoff = _parse_kickoff(fx.kickoff_utc)
            buckets.setdefault((h, a, league_key), []).append((source_name, fx, kickoff))

    # Exact-key bucketing alone leaves one fixture split across several keys
    # whenever sources name a club differently in a way normalisation cannot
    # fully collapse ("Coventry" vs "Coventry City"). Those split buckets each
    # look single-source, so genuinely corroborated fixtures were reported as
    # unverified -- the 2026-09-06 symptom this module was written for, which
    # normalisation alone did not fix.
    #
    # Merge buckets that denote the same fixture: same league, and both teams
    # matching under names_match. Keys are folded into the LONGEST-named
    # representative, so the surviving record carries the most specific names
    # rather than whichever source happened to be read first.
    merged: dict = {}
    for key in sorted(buckets, key=lambda k: (-len(k[0]) - len(k[1]), k)):
        h, a, league_key = key
        target = None
        for existing in merged:
            eh, ea, eleague = existing
            if eleague == league_key and names_match(eh, h) and names_match(ea, a):
                target = existing
                break
        if target is None:
            merged[key] = list(buckets[key])
        else:
            merged[target].extend(buckets[key])
    buckets = merged

    results: list = []
    for (h, a, _league_key), entries in buckets.items():
        league_display = next((fx.league for _, fx, _ in entries if fx.league), "")

        known = sorted([e for e in entries if e[2] is not None], key=lambda e: e[2])
        unknown = [e for e in entries if e[2] is None]

        clusters: list = []
        for entry in known:
            placed = False
            for cluster in clusters:
                if abs(cluster["kickoff"] - entry[2]) <= kickoff_tolerance:
                    cluster["entries"].append(entry)
                    placed = True
                    break
            if not placed:
                clusters.append({"kickoff": entry[2], "entries": [entry]})

        if unknown:
            # Can't confirm agreement for an unparseable kickoff -- attach
            # to the sole cluster if there is exactly one (team+league match
            # is still meaningful), otherwise it's its own ambiguous group.
            if len(clusters) == 1:
                clusters[0]["entries"].extend(unknown)
            else:
                clusters.append({"kickoff": None, "entries": unknown})

        if len(clusters) <= 1:
            cluster = clusters[0] if clusters else {"kickoff": None, "entries": []}
            sources = {name: fx for name, fx, _ in cluster["entries"]}
            tier = VerificationTier.VERIFIED if len(sources) >= 2 else VerificationTier.SINGLE_SOURCE
            results.append(MatchedFixture(
                home=h, away=a, league=league_display,
                kickoff_utc=cluster["kickoff"], sources=sources, tier=tier,
            ))
        else:
            all_sources = {}
            conflict_detail = []
            for cluster in clusters:
                for name, fx, kickoff in cluster["entries"]:
                    all_sources[name] = fx
                    conflict_detail.append({
                        "source": name,
                        "kickoff_utc": kickoff.isoformat() if kickoff else None,
                    })
            results.append(MatchedFixture(
                home=h, away=a, league=league_display,
                kickoff_utc=None, sources=all_sources,
                tier=VerificationTier.CONFLICT, conflict_detail=conflict_detail,
            ))

    return results


def unmatched_report(matched: list) -> dict:
    """Diagnostic aid, not a display artifact: shows single-source and
    CONFLICT fixtures separately, so you can eyeball whether a single-source
    case is genuinely unique to one source (or a normalization miss needing
    an alias in TEAM_ALIASES), and see exactly what each source disagreed
    on for any CONFLICT."""
    singles = [mf for mf in matched if mf.tier == VerificationTier.SINGLE_SOURCE]
    conflicts = [mf for mf in matched if mf.tier == VerificationTier.CONFLICT]
    return {
        "total_fixtures": len(matched),
        "verified_2plus": sum(1 for mf in matched if mf.tier == VerificationTier.VERIFIED),
        "single_source": len(singles),
        "conflict": len(conflicts),
        "single_source_detail": [
            {
                "home": mf.home,
                "away": mf.away,
                "league": mf.league,
                "only_source": next(iter(mf.sources)),
            }
            for mf in singles
        ],
        "conflict_detail": [
            {
                "home": mf.home,
                "away": mf.away,
                "league": mf.league,
                "disagreement": mf.conflict_detail,
            }
            for mf in conflicts
        ],
    }


if __name__ == "__main__":
    # Test 1: normalization fixing a would-be miss -- should VERIFY.
    flashscore = [SourceFixture("Man Utd", "Chelsea FC", "Premier League", "2026-09-06T15:00:00Z")]
    bbc = [SourceFixture("Manchester United", "Chelsea", "Premier League", "2026-09-06T15:00:00Z")]
    result = match_fixtures({"flashscore": flashscore, "bbc": bbc})
    print("Test 1 (should verify):", unmatched_report(result))
    # Expect: total_fixtures=1, verified_2plus=1, single_source=0, conflict=0

    # Test 2: same teams/league, kickoff times disagree by more than
    # tolerance -- should CONFLICT, not silently split or falsely verify.
    apif = [SourceFixture("Rangers", "Celtic", "Scottish Premiership", "2026-09-06T15:00:00Z")]
    tsdb = [SourceFixture("Rangers FC", "Celtic FC", "Scottish Premiership", "2026-09-06T19:30:00Z")]
    result2 = match_fixtures({"api_football": apif, "thesportsdb": tsdb})
    print("Test 2 (should conflict):", unmatched_report(result2))
    # Expect: total_fixtures=1, verified_2plus=0, conflict=1, with both
    # sources' reported kickoff times shown in conflict_detail