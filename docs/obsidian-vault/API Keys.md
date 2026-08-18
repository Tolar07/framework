# API Keys & Credentials — OLP XDV

> **CONFIDENTIAL — do not commit, do not paste into chat, do not share.**
> This note is the canonical store for every live credential used by the OLP XDV
> pipeline. It mirrors `.env` (the runtime source of truth) and is stored here so
> the Architect has one safe place to look when a key needs rotating or
> re-pasting after a rebuild.
>
> **Source of truth:** `olp_xdv_agent/olp_xdv/.env` (gitignored, never committed).
> This note is a *copy* for safekeeping — when a key changes, update `.env`
> first, then this note. When this note changes, update `.env`.
>
> **Lifecycle convention:** `.env.example` carries placeholders and stay
> git-tracked; `.env` carries real values and stays gitignored.

## Live keys (verified 2026-08-12)

| Service | Env var | Value | Plan / notes |
|---|---|---|---|
| The Odds API | `<REDACTED>` | `<REDACTED>` | **PRIMARY** — personal paid key, set 2026-08-11 (Architect decision). MES entry price source. Free-tier backups (`ODDS_API_KEY_BACKUP`, `<REDACTED>`) are commented out and currently empty. |
| TheSportsDB | `<REDACTED>` | `5558126822` | Registered free key. Fallback public test key `123` is rate-limited and truncates the league list. |
| Telegram Bot | `<REDACTED>` | `<REDACTED>` | `@BotFather` → `/newbot`. Daily board delivery + command responses. |
| Telegram chat | `<REDACTED>` | `8074295061` | Found by messaging the bot once, then reading `getUpdates`. |
| API-Football | `<REDACTED>` | `<REDACTED>` | **FREE plan** (verified 2026-08-12 via `/status` → `"plan":"Free"`, end 2027-08-03). Free serves seasons **2022–2024 only** — promoted clubs and post-2024 teams fall to NO DATA. Paste a PAID Standard/Pro key here to load current-season ratings (code auto-enables, plan-gated, `data/api_football_plan.py`, fails closed). |
| Admin dashboard | `<REDACTED>` | `architect` | HTTP Basic auth on `/admin`, `/stats`, `/why`, `/api/admin/*`, `POST /api/trigger-board`. |
| Admin dashboard | `<REDACTED>` | `j6!SUy%4T&PSVz%bcKin9GTE` | **Strong generated 2026-08-12** — 24 chars, ~140 bits entropy. Stored in `scripts/generate_admin_pass.py` for future rotation. Rotate yearly or on any leak. |
| Anthropic | `<REDACTED>` | *(blank — not yet set)* | Optional webapp AI Analyst chat (`/api/analyst`). Leave blank to keep the panel honestly "unavailable" rather than degrade silently. Requires the `anthropic` package (in `requirements.txt`). |

## MCP Server keys (verified 2026-08-12)

Stored at the workspace root (`C:\Users\Motunrayo\omniroute test\.env`), separate
from the pipeline `.env`. These power the Claude Code MCP servers (Perplexity,
Firecrawl), not the OLP XDV pipeline itself.

| Service | Env var | Value | Notes |
|---|---|---|---|
| Perplexity | `<REDACTED>` | `<REDACTED>` | Real-time web search + reasoning. Get one: https://www.perplexity.ai/settings/api |
| Firecrawl | `<REDACTED>` | `<REDACTED>` | Web scraping, crawling, extraction. Free tier available at https://firecrawl.dev |
| Firecrawl endpoint | `<REDACTED>` | `https://api.firecrawl.dev` | Optional; only set for self-hosted. |
| Chrome MCP | — | *(no key needed)* | Requires Chrome/Edge + Playwright Extension; launch with `--extension` flag. |

## Disabled / killed channels (do NOT re-enable)

| Channel | Status | Notes |
|---|---|---|
| WhatsApp (Meta Cloud API) | **KILLED 2026-08-06** (Architect order, ID412) | Recurring token-expiry + template-approval pain; web dashboard replaced it. `WHATSAPP_ENABLED=0`. Credentials (`WHATSAPP_TOKEN`, `<REDACTED>`, `WHATSAPP_TO`, `<REDACTED>`, `WHATSAPP_LANGUAGE`) are commented out in `.env` so the channel cannot send even if the flag is flipped. **Do not re-enable without Architect approval.** |
| Email (SMTP via Gmail app-password) | OFF (commented) | `EMAIL_USER`, `EMAIL_APP_PASSWORD`, `EMAIL_TO`, `EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT` all commented. Leave OFF unless explicitly ratified. |
| football-data.org | Not set (commented) | `<REDACTED>` placeholder. Register free at https://www.football-data.org/client/register — 10 req/min, 100 req/day, sufficient for current-season results. P0 fix for promoted-club ratings (2026-08-12). |

## Flags that gate these keys (not secrets themselves, but control behavior)

| Flag | Value | Effect |
|---|---|---|
| `<REDACTED>` | `1` | Basic auth ON for `/admin` + `/stats` + `/why` + `/api/admin/*` + `/api/trigger-board`. Set `0` only for local dev — the admin view exposes full model internals on a phone-reachable host. |
| `<REDACTED>` | `1` | **Override active** — publishes boards to the client *before* the CLV gate is met (gate is 12/30 legs, mean CLV currently −1.631%, NOT met). Override is never silent: `write_published` stamps the live gate numbers + override flag into `publish_audit.jsonl`; honest-edge statement stays in the client view. Set `0` to re-block. |
| `<REDACTED>` | `0` | Bot pushes only the daily run + command responses. Monitor alerts (health/watchdog/dead-man's-switch) log locally but do NOT message Telegram unless this is `1`. |

## Rotation checklist

When a key needs rotating:
1. Generate the new key at the provider's dashboard.
2. Update `olp_xdv_agent/olp_xdv/.env` (or `C:\Users\Motunrayo\omniroute test\.env` for MCP server keys) with the new value.
3. Update this note's **Live keys** / **MCP Server keys** table to match.
4. If the old key was paid, revoke it at the provider.
5. Re-run the pipeline / MCP server to confirm the new key loads.

## Gitignore confirmation

`.env` is in `.gitignore` at both the workspace root and inside `olp_xdv_agent/olp_xdv/` — verified. `.env.example` files (placeholders only, no real values) are git-tracked and safe. **Never commit `.env`.** If a `git status` ever shows `.env` as staged, abort and investigate — that would leak every key here.

## Related vault notes

- [[OLP XDV.md]] — vault home / entry point
- [[Decisions Log.md]] — includes the 2026-08-11 key-priority decision (paid Odds API key as primary)
- [[Protected Constants.md]] — `ARCHITECT_SIGNOFF`, the publish gate, and why these keys must not be silently rotated to change published outputs
- [[Rules.md]] — HR35 (no fabrication) and the honest-edge bright lines these keys feed
- [[Architecture.md]] — the pipeline stages each key fuels (see "Keys that fuel each stage")
- [[Agents.md]] — which agents access which keys (never self-approve rotation)
- [[Open Questions.md]] — item 3 (quota reset timing + backup key)
- [[OLP_XDV_Framework_Index.md]] — the .env file paths in the real repo
- [[README.md]] — what the vault is + how to use it
