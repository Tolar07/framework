"""/yt_ok and /yt_veto (output/telegram_commands.py): the Architect's votes on the YouTube bot's review queue.
The Architect's chat only, fails closed; a vote is one line in the vote log. No network, no private data."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from output import telegram_commands as tc  # noqa: E402

OWNER = "4242"


def _setup() -> Path:
    os.environ["TELEGRAM_CHAT_ID"] = OWNER
    tc.YT_VOTES_FILE = Path(tempfile.mkdtemp()) / "memory" / "youtube_votes.jsonl"
    return tc.YT_VOTES_FILE


def _votes(p: Path) -> list[dict]:
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def test_ok_and_veto_are_recorded_from_the_owner_chat():
    p = _setup()
    assert tc.handle("/yt_ok sh-1114-l", OWNER).startswith("APPROVED SH-1114-L")
    assert tc.handle("/yt_veto BB-1114-A extra words", OWNER).startswith("REFUSED BB-1114-A")
    got = _votes(p)
    assert [(v["id"], v["vote"]) for v in got] == [("SH-1114-L", "ok"), ("BB-1114-A", "veto")]
    assert all(v["at"].endswith("Z") and len(v["at"]) == 20 for v in got)


def test_only_the_architects_chat_votes_and_it_fails_closed():
    p = _setup()
    for chat in ("999", None, ""):
        assert tc.handle("/yt_ok SH-1114-L", chat).startswith("REFUSED — YouTube videos")
        assert tc.handle("/yt_veto SH-1114-L", chat).startswith("REFUSED — YouTube videos")
    os.environ["TELEGRAM_CHAT_ID"] = ""                      # no owner chat configured: nobody can vote
    assert tc.handle("/yt_ok SH-1114-L", OWNER).startswith("REFUSED — YouTube videos")
    assert _votes(p) == []
    os.environ["TELEGRAM_CHAT_ID"] = OWNER


def test_a_bad_id_records_nothing():
    p = _setup()
    for bad in ("", "MD-3", "SH-1114", "SH-1114-L2", "../x", "SH-11145-L", '{"id":1}'):
        assert tc.handle(f"/yt_ok {bad}", OWNER).startswith("Usage: /yt_ok")
    assert tc.handle("/yt_veto", OWNER).startswith("Usage: /yt_veto")
    assert _votes(p) == []


def test_help_lists_the_commands_and_other_votes_are_untouched():
    _setup()
    assert "/yt_ok" in tc.cmd_help("") and "/yt_veto" in tc.cmd_help("")
    assert tc.handle("/veto", OWNER).startswith("Usage: /veto")          # the money desk's own command still routes
    assert "/yt_ok" not in tc.HANDLERS and "/yt_veto" not in tc.HANDLERS  # never reachable without the chat guard


def main() -> None:
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("youtube_votes_test OK")


if __name__ == "__main__":
    main()
