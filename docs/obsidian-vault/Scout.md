# Scout (2026-11-03)

Recorded-only section of the reasoning step (`engine/scout.py`). Gemini + Google Search, with the NVIDIA / OpenRouter `:free` fallback, looks per fixture for team news, injuries, line-ups, late line moves and X chatter. Output: `output/reasoning/scout_*.json`. Graded into `memory/scout_record.json`; one "Scout" line in the 23:02 UK bot report.

- Changes no pick, stake, threshold, CLV gate or verdict. Failure = the step goes on as before.
- Kill switch: repo variable `SCOUT_ENABLED=0`.
- Affecting picks (2026-11-03): a starter the scout reports OUT counts only when FotMob lists him out too. Each confirmed absence is signed on every pick (keeper/defender out: more goals, his side weaker; forward out: fewer goals, his side weaker). Shadow strategies S10 / A8 / T8 drop what it hurts; they reach the board only by beating it on CLV and return over 100+ graded bets (order 45).
- Scored fairly: a board counts only confirmations made before it was built (`confirmed_at`).
