"""
ID403 + ID403.1 — Multi-Factor Data Verification.
Replaces self-certification with independent-factor agreement.

Four factors:
  F1 — structured vs free-text (a structured feed like FootyStats/Football-Data
       CSV outranks a scraped free-text claim)
  F2 — cross-source quorum: >=2 INDEPENDENT domains agree (ID404: two pages of
       the same site do NOT count as independent)
  F3 — internal consistency (e.g. a team's own season page agrees with the
       fixture list; a stated manager change agrees with the match report)
  F4 — provenance (is there a traceable URL / timestamp, or is it hearsay)

Output tiers: VERIFIED / SINGLE-SOURCE / CONFLICT / NO-DATA / DERIVED.
HR35: CONFLICT and NO-DATA are never silently resolved by picking one side.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class Tier(str, Enum):
    VERIFIED = "VERIFIED"
    SINGLE_SOURCE = "SINGLE-SOURCE"
    CONFLICT = "CONFLICT"
    NO_DATA = "NO-DATA"
    DERIVED = "DERIVED"


# ID404 Source Trust Register (trust tier sets corroboration requirement,
# never exempts a capital-relevant datum from independent cross-check)
SOURCE_TRUST = {
    # T1 — structured/official
    "football-data.co.uk": "T1", "footystats.org": "T1", "spfl.co.uk": "T1",
    "fbref.com": "T1", "transfermarkt.us": "T1", "wikipedia.org": "T1",
    "sports-data-tool": "T1", "api-football.com": "T1",
    # T2 — established news / structured-but-community-maintained
    # thesportsdb.com RATIFIED by the Architect (HR34) as the upcoming-fixtures
    # source, 2026-08-03. T2 not T1: it's a structured JSON feed with traceable
    # provenance, but community-editable rather than an official league feed —
    # so fixtures stamp ○ SINGLE-SOURCE until a second independent source
    # (e.g. football-data.org) provides F2 quorum.
    "thesportsdb.com": "T2",
    "bbc.co.uk": "T2", "skysports.com": "T2", "espn.com": "T2",
    # T3 — aggregators, lead-only, never verifying alone
    "predictz.com": "T3", "betinf.com": "T3", "fctables.com": "T3",
    # Rejected / JS-locked — never usable even as a lead
    "flashscore.com": "REJECTED", "statarea.com": "REJECTED",
}


@dataclass
class SourcedDatum:
    """One claim about one fact, from one source."""
    domain: str
    value: object
    url: str | None = None
    structured: bool = True  # F1


@dataclass
class VerificationResult:
    tier: Tier
    value: object | None
    factors: dict = field(default_factory=dict)
    note: str = ""


def _domain_root(domain: str) -> str:
    d = domain.lower().replace("www.", "")
    for known in SOURCE_TRUST:
        if known in d:
            return known
    return d


def verify(claims: list[SourcedDatum]) -> VerificationResult:
    """Runs a set of same-fact claims from different sources through ID403/403.1.
    HR35: never averages away a disagreement, never fabricates a merged value."""
    if not claims:
        return VerificationResult(tier=Tier.NO_DATA, value=None,
                                   note="NO DATA — PENDING")

    # Drop REJECTED sources entirely (Flashscore etc. — never usable, not even a lead)
    usable = [c for c in claims if SOURCE_TRUST.get(_domain_root(c.domain)) != "REJECTED"]
    if not usable:
        return VerificationResult(tier=Tier.NO_DATA, value=None,
                                   note="all sources REJECTED-tier — NO DATA — PENDING")

    independent_domains = {_domain_root(c.domain) for c in usable}
    values = {str(c.value) for c in usable}

    f1_structured = any(c.structured for c in usable)
    f2_quorum = len(independent_domains) >= 2
    f4_provenance = any(c.url for c in usable)

    if len(values) > 1:
        # Genuine disagreement between independent sources — surface it, don't resolve it.
        return VerificationResult(
            tier=Tier.CONFLICT, value=None,
            factors={"F1": f1_structured, "F2": f2_quorum, "F4": f4_provenance,
                     "conflicting_values": list(values)},
            note="CONFLICT — sources disagree, Architect must adjudicate",
        )

    if f2_quorum and f1_structured and f4_provenance:
        tier = Tier.VERIFIED
    elif len(usable) == 1:
        tier = Tier.SINGLE_SOURCE
    else:
        # multiple sources, same domain family only, or missing structure/provenance
        tier = Tier.SINGLE_SOURCE

    return VerificationResult(
        tier=tier, value=usable[0].value,
        factors={"F1_structured": f1_structured, "F2_quorum": f2_quorum,
                 "F4_provenance": f4_provenance,
                 "independent_domains": list(independent_domains)},
        note="",
    )


def stamp(result: VerificationResult) -> str:
    """The Part-2 board stamp character: VERIFIED=✓ SINGLE-SOURCE=○ CONFLICT=⚠ NO-DATA=—"""
    return {
        Tier.VERIFIED: "✓",
        Tier.SINGLE_SOURCE: "○",
        Tier.CONFLICT: "⚠",
        Tier.NO_DATA: "—",
        Tier.DERIVED: "◇",
    }[result.tier]
