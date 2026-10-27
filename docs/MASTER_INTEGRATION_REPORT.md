# OLP XDV — Master Integration Report

> Written 2026-10-27 from the Architect's "Comprehensive Master Integration Report" (v116.00), **corrected against the code
> on `main` (d4fa379e)**. Where the original and the code disagree, the code wins and the difference is listed in
> section 8. Companion vault note: `docs/obsidian-vault/Master Integration Report.md`.

## 1. Summary

OLP XDV is a **live-capital** football (and NBA) system: a GitHub-Actions pipeline in `Tolar07/framework` (public)
builds a board of priced picks, SportyBet booking codes and accas; separate private bots place real stakes.
The framework itself never logs in to a betting account (standing order 26); placing is done by `sportybet-agent` and
`matchbook-agent` under their own bright-line amendments. `config.PHASE = 3`, `CAPITAL_ENABLED = PHASE >= 3`.
Protected: `ARCHITECT_SIGNOFF`, the CLV gate, capital deployment, and the protected files listed in `CLAUDE.md`.

## 2. Repositories (GitHub `Tolar07/…`)

| Repo | Vis. | Role |
|---|---|---|
| `framework` | public | Pipeline, engine models, board, Telegram commands, graders. Actions minutes are unmetered. |
| `matchbook-agent` | private | Matchbook live bot (£50, back bets, ½-Kelly), in-play bot, steam signals, PC jobs (`pc/`), caretaker. Runner `matchbook-uk` (Windows) and the Oracle VM Linux runner. |
| `sportybet-agent` | private | SportyBet placer, steam, in-play, live cash-out loop. Split out of matchbook-agent 2026-10-25. Runner `sportybet-oracle` (+ `sportybet2` for account 2). |
| `olp-whatsapp` | private | WhatsApp mirror (board/codes/results → "Olpxdv" channel + one bundled DM). Runner `whatsapp-oracle`. |
| `omniroute-test` | private | The PC workspace: `CLAUDE.md`, scripts (`llm-run.ps1`, `claude-auto.ps1`), the framework as a submodule at `olp_xdv_agent/olp_xdv/`. `main` is the only live line. |
| `closing_edge`, `CLV-log-and-framework-docs` | private | Supporting CLV research / docs; not in the live path. |

**There is no Trading 212 repo, bridge or executor** (see section 8).

Framework tree (top level that matters): `engine/` models and learning · `pipeline/` odds and booking sources ·
`data/` fixtures/results sources · `output/` board, picks, Telegram commands (`telegram_commands.py`) · `monitor/` the
loops (commands, live, news, universe, watchdog, supervisor…) · `bets/`, `booking/`, `clv/` · `backtest/` ·
`memory/` JSON state · `tests/` · `.github/workflows/` · `.claude/agents/`.

## 3. The ten agents (`.claude/agents/olp-xdv-NN-*.md`)

Domain-owner prompts, not processes. 01 Ingestion (fixtures) · 02 List/filter (leagues, eligibility) · 03 Entity
profiling (form, team news) · 04 Data verification (ID403 source tiers) · 05 XDV core (the models) · 06 Odds audit
(SportyBet primary, football-data/Odds API fallbacks, drift guard) · 07 Compliance (bright lines, market gate, standing
orders) · 08 Execution (booking codes, staking) · 09 Team lead (board and delivery) · 10 CEO (grading, learning, report).
Also in the folder: `olp-xdv-supervisor` (multi-session state via `docs/STATE.md`), `olp-xdv-specialist`, and generic
reviewers (architect, planner, code-reviewer, security-reviewer, tdd-guide, devops-troubleshooter, fixtures-checker,
conversation-auditor).

## 4. Engine models (`engine/`)

Dixon-Coles goals model (`dixon_coles.py`, recency-weighted) · Elo second opinion (`elo.py`, `national_elo.py`) · xG and
shots-on-target (`xg_model.py`, `sot_model.py`) · Platt scaling on the logit (`calibration.py`: `sigmoid(A + B·logit(raw))`) ·
MES, the numerical Market Edge Score every capital pick must carry (`mes.py`, HR30) · cross-league (`cross_league.py`) ·
sharp-line value (`sharp_value.py`, `market_implied.py`) · kickoff cohorts for accas (`cohorts.py`, order 46) ·
CLV accas (`clv_accas.py`) · experiments with auto-promotion (`experiments.py`, order 45) · nightly refit (`retrain.py`) ·
reasoning/verdict (`reasoning.py`, `cognitive_core.py`) · NBA (`nba_*`) · staking (`staking.py`).

## 5. Loops and workflows

GitHub drops and delays crons, so most workflows are **chains**: each run starts the next, and the cron is only a backup
starter. Times are UTC in the file; UK time in brackets.

| Workflow | Schedule in the file | What it does |
|---|---|---|
| `daily.yml` | 20:47 + 21:47, 05:47 + 06:47 (BST/GMT pair → 21:47 and 06:47 UK) | Evening prep board and morning refresh; starts the live, news and universe loops. A slot that fires early exits without sending. |
| `clock.yml` | `13 */2` + slot restarts (20:31, 05:31, 21:31, 06:31) | Board clock; restarts the chain if it died. |
| `live.yml` | 11:09, 14:09, 17:09, 19:09 | Matchday tracker (`monitor/live_loop.py`); normally started by `daily.yml`. |
| `nba_live.yml` / `nba_watch.yml` | `9 16,19,22,1,4` / `5 16,19,22` | NBA live tracker and price watch. |
| `news.yml` | `5 9,11,13,15,17,19` | Team-news loop. |
| `universe.yml` | `20 */3` | 3-hourly sweep and grading. |
| `commands.yml` | `5 * * * *` hourly **starter**; one job then **loops every 5 min** (`monitor/commands_loop.py`) | Telegram commands. |
| `watchdog.yml` | 21:23, 22:23, 23:17, 06:23, 07:23, 08:17 | Checks each slot delivered; opens an auto-fix issue. |
| `reasoning.yml` | 22:17 | Gemini verdict run. |
| `retrain.yml`, `match_study.yml`, `profiles.yml`, `weekly.yml`, `backtest.yml`, `matchbook_ledger.yml`, `study_send.yml`, `supervisor.yml`, `research_note.yml`, `tests.yml`, `claude-review.yml` | various | Refit, studies, profiles (Mon 04:41), weekly review (Mon 07:51), monthly backtest (2nd, 12:13), Matchbook ledger (05:23), CI. |

**Telegram commands** (`output/telegram_commands.py`): `/start /help /status /board /picks /verify /why /log /note
/lookup /debrief /proposals /approve /reject`.

## 6. Beyond the framework (missing from the original report)

- **sportybet-agent.** Hourly placer chain at 22:00 UK for the next day's codes (workflow `sportybet-placer.yml`, runner
  `sportybet-oracle`, state `/var/lib/sportybet_state`). Live since 2026-10-25. Loops: **steam** (every 10 min, ₦10,000 pot,
  ₦1,000 a bet, from Matchbook's `steam_signals.json`), **in-play** (every 10 min, own ₦10,000 pot), **cash-out** (live
  ticket monitor), and `sportybet-live.yml`, a loop running cash-out every 5 min and in-play every 10. **Two accounts**:
  `sportybet2-*` workflows (placer, steam, in-play, live, cash-out) run on the `sportybet2` runner label, gated by repo
  variable `SB_ACCOUNT2 == '1'`. Only one repo may hold `SPORTYBET_HOST=linux`. Never twice: SportyBet's bet history decides.
- **matchbook-agent.** `matchbook-agent-linux.yml` every ~5 min, live switch = repo variable `MATCHBOOK_LIVE`, `STOP` file
  halts; watchdog and caretaker; `pc/` jobs run from `C:\olp\mb-agent`, kept current by `pc/pc_watchdog.py` every 15 min.
- **Oracle VM runners:** the Matchbook Linux runner, `sportybet-oracle`, `whatsapp-oracle`; the PC keeps the Windows
  `matchbook-uk` service and the fixer.
- **olp-whatsapp.** `mirror.yml` chain under `xvfb-run`, posts only when `WHATSAPP_HOST=linux`; own watchdog.
- **OmniRoute / `llm-run.ps1`.** PC background text jobs run on OmniRoute (`localhost:20128`, `auto/pro-coding`) and fall
  back to Sonnet; browser jobs go straight to Sonnet; every run is logged to `%USERPROFILE%\llm-router.log`.
  `scripts/claude-auto.ps1` switches interactive Claude Code to OmniRoute while the usage limit is spent.
- **Watchdog → fixer.** Failures open a sticky auto-fix issue; a fixer routine fixes and merges; Telegram only if unfixed
  after 3 h or catastrophic.

## 7. Developer instructions

```bash
cd olp_xdv_agent/olp_xdv
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python tests/run_all.py                                 # each tests/*.py in its own process; CI uses Python 3.12
python run_daily.py --only-production --heartbeat --target-date YYYY-MM-DD
# other run_daily.py flags: --season --fixtures-season --leagues --min-mes --no-send --next-day --slot --refreeze
```

CI (`tests.yml`) also runs ruff on `monitor/json_log.py` and mypy. Real credentials live in `.env` / GitHub secrets only.
Set secrets from Git Bash (`printf '%s' "$v" | gh secret set`), never by piping from PowerShell 5.1.
Ship rule: branch → PR → green CI → merge; commit with `git commit --only <paths>`.

## 8. Corrections to the original report

| Original | Code says |
|---|---|
| `commands.yml` polls every 5 min | The cron is an **hourly starter** (`5 * * * *`); the single job it starts loops every 5 min. |
| Agent 07 "paper-only assertions" | **Outdated.** Live capital since 2026-10-03 (order 26), live-not-paper for everything since 2026-10-26 (order 46: "Everything goes live"). `assert_paper_only()` still exists in `config/__init__.py` but `PHASE = 3`. |
| T212 environment / bridge | **No Trading 212 repo, bridge or executor exists**; nothing in the code references one. Not documented as a feature. |
| Report ended at framework + agents | Omitted sportybet-agent (two accounts, steam/in-play/cash-out), the Oracle VM runners, olp-whatsapp, OmniRoute/`llm-run` — added in section 6. |
| `universe.yml` 3-hourly, `daily.yml` 20:47/05:47 UTC | Confirmed, plus the GMT twins at 21:47/06:47 UTC. |
| Command list `/status /board /verify /why /log /note /debrief /proposals /approve /reject` | Confirmed; code also has `/start /help /picks /lookup`. |
