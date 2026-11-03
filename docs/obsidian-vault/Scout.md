# Scout (2026-11-03)

Recorded-only section of the reasoning step (`engine/scout.py`). Gemini + Google Search, with the NVIDIA / OpenRouter `:free` fallback, looks per fixture for team news, injuries, line-ups, late line moves and X chatter. Output: `output/reasoning/scout_*.json`. Graded into `memory/scout_record.json`; one "Scout" line in the 23:02 UK bot report.

- Changes no pick, stake, threshold, CLV gate or verdict. Failure = the step goes on as before.
- Kill switch: repo variable `SCOUT_ENABLED=0`.
- It earns a say only if its record (Brier / log-loss against the market) shows it, and only on the Architect's instruction.
