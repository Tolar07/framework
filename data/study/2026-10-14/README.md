# 14 Oct 2026 — study board (not the live board)

Same exercise as 13 Oct (Architect 2026-10-13: "do that again and ... send [it to] Telegram so I can follow up"):
every fixture of the live board's day (9 Champions League, 4 Championship), one market each, no market
repeated, BTTS called per fixture, scored by the engine on P(win) (`engine_board.py`, Run ID STUDY-dab19260,
SportyBet fetched 2026-10-13T21:21:03Z), booked by `book_all.py`.

New this time — the 13 Oct lessons as study filters (not live-board rules): no team Under on a side the
strength-adjusted profile expects to score more than 1.3 goals; no match Under when the profile reads
BTTS yes / Over. Each fixture's profile read is saved with its leg.

- `engine_board.json` — every leg, its profile read, how many Under candidates the lessons removed
- `study_codes.json` — every SportyBet code: singles, accas A–D, the mega, BTTS calls and slips
- `telegram.txt` — the message sent to the Architect's own chat (`study_send.yml`)
