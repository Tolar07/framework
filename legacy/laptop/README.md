# Parked laptop-line code (2026-10-03)

Everything here came in from the laptop line (`elo-persistence`) in the
lineage merge (#47) and is **not used by the live framework**: no module the
daily board, Telegram commands, news check, backtests or revived features
import depends on it. It is kept on purpose, not deleted.

Paths mirror where each file used to live (`legacy/laptop/booking/bridge.py`
was `booking/bridge.py`). This covers the laptop's Stage A/B pipeline
(`pipeline/fixture_extraction.py`, `orchestrator_DEPRECATED.py`), the web
dashboard (`webapp/`), the booking bridge and SportyBet scrapers (`booking/`),
the extra data sources (`data/`), steward, sandbox, email/WhatsApp delivery,
one-off scripts and their tests. `legacy/laptop/.github/workflows/` holds the
laptop's Stage A workflow; GitHub does not run workflows from this folder.

The live framework is everything outside `legacy/`. To bring a feature back,
move it into the live tree as a normal PR, port it to the live modules it
needs, and move its test back into `tests/` so CI covers it.
