"""Telegram markdown-parse fallback (regression for the 2026-08-17 CI failure).

The board is split into chunks and sent with parse_mode=Markdown. An unbalanced
markdown entity (a `*`/`_`/`#` left at a chunk boundary) makes Telegram reject
the part with "Bad Request: can't parse entities". That is NOT transient — the
same markup would fail forever. Before the fix, send_telegram returned ok=False
on the first such part, which made run_daily raise and abort the WHOLE daily
run (so the board never reached the phone at all).

The fix: when a part fails with a parse error, re-send THAT part as plain text
(parse_mode omitted). A complete plain board beats a never-delivered one.
No network — requests.post is mocked.
"""
import os
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from output import notify


class _FakeResp:
    def __init__(self, ok: bool, description: str = ""):
        self._ok = ok
        self._d = description

    def json(self):
        return {"ok": self._ok, "description": self._d}


def test_markdown_parse_error_falls_back_to_plain() -> None:
    """A markdown parse failure on a part must fall back to plain text and
    deliver successfully, NOT abort the run."""
    seen = []

    def fake_post(url, json=None, timeout=30):
        seen.append(json.get("parse_mode"))  # None == plain text
        if json.get("parse_mode") == "Markdown":
            return _FakeResp(
                False,
                "Bad Request: can't parse entities: Can't find end of the "
                "entity starting at byte offset 2089")
        return _FakeResp(True)

    with mock.patch.object(notify.requests, "post", fake_post):
        ok, notes = notify.send_telegram(
            "a board with unbalanced **bold that telegram cannot parse",
            token="X", chat_id="Y")
    assert ok is True, f"plain fallback must deliver; notes={notes}"
    assert seen == ["Markdown", None], f"expected Markdown then plain; got {seen}"
    assert any("delivered" in n for n in notes), notes
    print("1. markdown parse error -> plain-text fallback -> delivered: OK")


def test_other_errors_still_fail_after_retries() -> None:
    """A NON-parse error (e.g. network) must still fail after retries — we must
    not silently swallow real delivery problems as 'plain text works'."""
    def fake_post(url, json=None, timeout=30):
        return _FakeResp(False, "Gateway Timeout")

    with mock.patch.object(notify.requests, "post", fake_post):
        ok, notes = notify.send_telegram("plain board body", token="X",
                                         chat_id="Y")
    assert ok is False, "non-parse error must still fail"
    assert any("FAILED" in n for n in notes), notes
    print("2. non-parse errors still fail (not swallowed): OK")


def test_multi_part_board_each_chunk_falls_back() -> None:
    """When the board splits into multiple parts and one has bad markup, only
    that part re-sends plain; the others still go Markdown and all deliver."""
    seen = []

    def fake_post(url, json=None, timeout=30):
        pm = json.get("parse_mode")
        seen.append(pm)
        # Make the SECOND part (a chunk boundary) fail markdown; others pass.
        text = json["text"]
        if pm == "Markdown" and "PART2_MARKDOWN_BAD *" in text:
            return _FakeResp(False, "can't parse entities")
        return _FakeResp(True)

    long_body = ("PART1 good\n" + "x" * 4000 + "\n"
                 "PART2_MARKDOWN_BAD *\n" + "y" * 2000 + "\n"
                 "PART3 good tail")
    with mock.patch.object(notify.requests, "post", fake_post):
        ok, notes = notify.send_telegram(long_body, token="X", chat_id="Y")
    assert ok is True, f"multi-part board must deliver; notes={notes}"
    # At least one plain fallback happened (the bad part).
    assert None in seen, f"expected a plain fallback; modes={seen}"
    print(f"3. multi-part board: bad chunk fell back to plain, rest delivered: OK ({seen})")


if __name__ == "__main__":
    test_markdown_parse_error_falls_back_to_plain()
    test_other_errors_still_fail_after_retries()
    test_multi_part_board_each_chunk_falls_back()
    print()
    print("✅ ALL TELEGRAM MARKDOWN-FALLBACK TESTS PASSED")
