"""monitor/multisport_live.py — every rollout sport's picks followed live. No network: feeds are faked."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor import multisport_live as L  # noqa: E402

NOW = datetime(2026, 11, 12, 20, 0, tzinfo=UTC)
TENNIS = {"sb_event_id": "sr:match:1", "home": "Sinner, Jannik", "away": "Alcaraz, Carlos",
          "ko": "2026-11-12T19:00:00Z", "market_id": "186", "specifier": "", "outcome": "Home",
          "pick": "Sinner, Jannik to win", "result": None}
HOCKEY = {"sb_event_id": "sr:match:2", "home": "Boston Bruins", "away": "Toronto Maple Leafs",
          "ko": "2026-11-12T19:30:00Z", "market_id": "18", "specifier": "total=5.5", "outcome": "Under 5.5",
          "pick": "Under 5.5", "result": None}
LATER = {**TENNIS, "sb_event_id": "sr:match:3", "ko": "2026-11-13T02:00:00Z"}      # > 3 h away: not yet
GRADED = {**TENNIS, "sb_event_id": "sr:match:4", "result": "won"}                   # already settled
KO_T = int(datetime(2026, 11, 12, 19, 0, tzinfo=UTC).timestamp())


def fs_block(aa: str, ab: str, home: str, away: str, ko: int, fh: int, fa: int, per: list[tuple[int, int]]) -> str:
    keys = (("BA", "BB"), ("BC", "BD"), ("BE", "BF"), ("BG", "BH"))
    f = [f"AA÷{aa}", f"AD÷{ko}", f"AB÷{ab}", f"AE÷{home}", f"AF÷{away}", f"AG÷{fh}", f"AH÷{fa}"]
    for (hk, ak), (h, a) in zip(keys, per, strict=False):
        f += [f"{hk}÷{h}", f"{ak}÷{a}"]
    return "¬".join(f)


def feed(*blocks: str) -> str:
    return "ZA÷LEAGUE¬~" + "~".join(blocks)


def tennis_game() -> list[dict]:
    return [{"key": "tennis:sr:match:1", "sport": "tennis", "home": TENNIS["home"], "away": TENNIS["away"],
             "ko": TENNIS["ko"], "picks": [TENNIS]}]


def board(tmp: Path):
    files = {("tennis", "2026-11-12"): {"picks": [TENNIS, GRADED]}, ("tennis", "2026-11-13"): {"picks": [LATER]},
             ("ice_hockey", "2026-11-12"): {"picks": [HOCKEY]}}

    def file_for(sport, day):
        p = tmp / f"{sport}_{day}.json"
        if (sport, day) in files:
            p.write_text(json.dumps(files[(sport, day)]), encoding="utf-8")
        return p
    return file_for


def test_board_games_window_and_graded():
    with tempfile.TemporaryDirectory() as d:
        games = L.board_games(NOW, board(Path(d)))
    keys = [g["key"] for g in games]
    assert keys == ["tennis:sr:match:1", "ice_hockey:sr:match:2"], keys


def test_parse_flashscore_live_states():
    evs = L.parse_flashscore_live(feed(fs_block("a", "2", "Sinner J.", "Alcaraz C.", KO_T, 1, 0, [(6, 4), (2, 1)]),
                                       fs_block("b", "1", "X", "Y", KO_T, 0, 0, [])))
    assert [e["state"] for e in evs] == ["in", "pre"]
    assert evs[0]["periods"] == [[6, 4], [2, 1]] and evs[0]["final"] == [1, 0] and evs[0]["winner"] is None


def test_a_set_won_then_the_final_with_where_each_pick_stands():
    games = tennis_game()
    seen: dict = {}
    rounds = [
        feed(fs_block("a", "1", "Sinner J.", "Alcaraz C.", KO_T, 0, 0, [])),
        feed(fs_block("a", "2", "Sinner J.", "Alcaraz C.", KO_T, 0, 0, [(3, 2)])),
        feed(fs_block("a", "2", "Sinner J.", "Alcaraz C.", KO_T, 1, 0, [(6, 4), (1, 0)])),
        feed(fs_block("a", "2", "Sinner J.", "Alcaraz C.", KO_T, 1, 0, [(6, 4), (3, 3)])),       # quiet
        feed(fs_block("a", "3", "Sinner J.", "Alcaraz C.", KO_T, 2, 0, [(6, 4), (6, 3)])),
    ]
    said = []
    still = True
    for text in rounds:
        feeds = {"tennis": {"flashscore": L.parse_flashscore_live(text), "espn": []}}
        lines, still = L.round_once(games, seen, None, feeds, NOW)
        said.append(lines.get("tennis", []))
    assert said[0] == []
    assert said[1][0].startswith("START") and "level / not decided" in said[1][1], said[1]
    assert said[2][0].startswith("END set 1") and "6-4" in said[2][0], said[2]
    assert "WINNING if it ended now" in said[2][1]
    assert said[3] == []
    assert said[4][0].startswith("FINAL") and said[4][1].startswith("  WON"), said[4]
    assert not still


def test_hockey_regulation_total_and_espn_fallback():
    games = [{"key": "ice_hockey:sr:match:2", "sport": "ice_hockey", "home": HOCKEY["home"], "away": HOCKEY["away"],
              "ko": HOCKEY["ko"], "picks": [HOCKEY]}]
    espn = {"events": [{"date": "2026-11-12T19:30Z", "status": {"type": {"state": "post", "name": "STATUS_FINAL"}},
                        "competitions": [{"competitors": [
                            {"homeAway": "home", "score": "4", "team": {"displayName": "Boston Bruins"},
                             "linescores": [{"value": 1}, {"value": 1}, {"value": 1}, {"value": 1}]},
                            {"homeAway": "away", "score": "3", "team": {"displayName": "Toronto Maple Leafs"},
                             "linescores": [{"value": 1}, {"value": 1}, {"value": 1}, {"value": 0}]}]}]}]}
    feeds = {"ice_hockey": {"flashscore": [], "espn": L.parse_espn(espn)}}
    lines, still = L.round_once(games, {}, None, feeds, NOW)
    out = lines["ice_hockey"]
    assert out[0].startswith("START") and out[1].startswith("FINAL")
    assert out[2].startswith("  LOST"), out            # regulation 3-3 = 6 goals: Under 5.5 lost
    assert not still


def test_no_feed_says_pending_once_never_guesses():
    games = [{**tennis_game()[0], "home": "Nobody A.", "away": "Nobody B."}]
    seen: dict = {}
    feeds = {"tennis": {"flashscore": [], "espn": []}}
    first, still = L.round_once(games, seen, None, feeds, NOW)
    again, _ = L.round_once(games, seen, None, feeds, NOW)
    assert first["tennis"][0].startswith("NO DATA — PENDING") and still
    assert again == {}


def test_handoff_resume_does_not_repeat():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "live.jsonl"
        text = feed(fs_block("a", "2", "Sinner J.", "Alcaraz C.", KO_T, 1, 0, [(6, 4), (1, 0)]))
        feeds = {"tennis": {"flashscore": L.parse_flashscore_live(text), "espn": []}}
        L.round_once(tennis_game(), {}, f, feeds, NOW)
        lines, _ = L.round_once(tennis_game(), L.resume([f]), f, feeds, NOW)
    assert lines == {}


def test_player_names_and_simulated_games():
    assert L.same_player("Julia Stusek", "Stusek J.") and L.same_player("Imai, Shintaro", "Imai S.")
    assert L.same_player("Alejandro Moro Canas", "Moro Canas A.")
    assert not L.same_player("Julia Stusek", "Ewald W.") and not L.same_player("A / B", "Stusek J.")
    fs = L.parse_flashscore_live(feed(fs_block("a", "2", "Chennai Super Kings", "Sunrisers Hyderabad", KO_T, 0, 0, [])))
    srl = {"key": "cricket:x", "sport": "cricket", "home": "Chennai Super Kings SRL",
           "away": "Sunrisers Hyderabad SRL", "ko": TENNIS["ko"], "picks": []}
    assert L.is_simulated(srl) and L.find_live(srl, {"flashscore": fs, "espn": []}) is None
    stusek = {"key": "tennis:y", "sport": "tennis", "home": "Julia Stusek", "away": "Weronika Ewald",
              "ko": "2026-11-12T19:00:00Z", "picks": []}
    late = L.parse_flashscore_live(feed(fs_block("b", "2", "Stusek J.", "Ewald W.", KO_T + 600, 0, 0, [])))
    assert L.find_live(stusek, {"flashscore": late, "espn": []}) is not None


def test_message_names_the_look():
    body = L.message({"tennis": ["FINAL a v b 2-0"]}, NOW)
    assert body.startswith("MULTI-SPORT LIVE · looked 20:00Z · run") and "\nTENNIS\nFINAL" in body


def test_every_rollout_sport_is_followed():
    roll = json.loads((L.ROOT / "config" / "sport_rollout.json").read_text(encoding="utf-8"))
    want = {x for s in roll["sports"] for x in (s.get("covers") or [s["sport"]])}
    assert want <= set(L.SPORTS) and want <= set(L.FS_SPORT)


def test_workflow_is_one_loop_started_by_the_clock():
    wf = (L.ROOT / ".github" / "workflows" / L.WORKFLOW).read_text(encoding="utf-8")
    assert "monitor/multisport_live.py" in wf and "timeout-minutes: 355" in wf and "actions: write" in wf
    assert "cron:" not in wf and "handoff" in wf and "concurrency:" not in wf


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("multisport_live_test: OK")
