"""docs/EVENT_MODELS_SCOPE.md (framework #560) ranks every sport the rollout covers, with scores that multiply."""
from __future__ import annotations

import re
from pathlib import Path

DOC = (Path(__file__).resolve().parent.parent / "docs" / "EVENT_MODELS_SCOPE.md").read_text(encoding="utf-8")
SPORTS = ["Ice hockey", "Baseball", "American football", "Cricket", "Darts", "Snooker", "Volleyball", "Rugby",
          "Table tennis"]


def _rows():
    out = {}
    for line in DOC.splitlines():
        m = re.match(r"\|\s*(\d)\s*\|\s*([^|]+?)\s*\|.*\|\s*(\d)\s*\|\s*(\d)\s*\|\s*(\d)\s*\|\s*$", line)
        if m:
            out[m.group(2)] = tuple(int(m.group(i)) for i in (1, 3, 4, 5))
    return out


def test_every_sport_listed_once():
    assert set(_rows()) == set(SPORTS)


def test_score_is_data_times_markets():
    for sport, (_, data, mk, score) in _rows().items():
        assert data * mk == score, sport


def test_scores_never_increase_down_the_ranking():
    # snooker (4) is ranked above volleyball (4) on purpose; no lower score sits above a higher one
    r = sorted(_rows().values())
    scores = [s for _, _, _, s in r]
    assert scores == sorted(scores, reverse=True)
