# OLP XDV Monitoring — Grafana + Prometheus

This folder contains a drop-in Grafana dashboard (`dashboard.json`) and a quickstart
for wiring the OLP XDV web dashboard's `/metrics` endpoint into Prometheus.

The web server is a stdlib-only `ThreadingHTTPServer`; it exposes plain-text
Prometheus exposition format at `GET /metrics`. No client library is used.

## 1. Prometheus scrape config

Add a scrape target to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'olp-xdv-web'
    static_configs:
      - targets: ['<host>:8088']   # or whatever --host/--port you ran the server on
    metrics_path: '/metrics'
    scrape_interval: 30s
```

If the server runs on the same host as Prometheus, `localhost:8088` works.
If it runs in Docker/WSL, use the correct reachable IP/hostname.

## 2. Import the dashboard

1. Open Grafana → **+** → **Import**
2. Paste the contents of `dashboard.json`
3. Pick the Prometheus data source you just added
4. Save

The dashboard shows:

- **Web Server Up** — 1/0, green/red
- **Published Boards** — count of client-visible board JSONs
- **Phase-3 Gate trajectory** — legs logged, legs with CLV, gate requirement (30), mean CLV %
- **Gate Met (pending Architect sign-off)** — boolean
- **Health State Severity** — one line per `health_state.json` key (quota, caches, env, etc.)
- **Last Run Age** — seconds since the monitor's last heartbeat (from `health_state.json`)
- **Process Uptime** — minutes this server process has been running

## 3. JSONL access logs (for Loki / log aggregation)

Every HTTP request also appends a single JSON line to `logs/web.jsonl`
(rotated at 5 MB, 2 backups). Example line:

```json
{
  "ts": "2026-08-09T14:32:10+01:00",
  "level": "info",
  "logger": "olp.json",
  "message": "127.0.0.1 \"GET /dashboard/2026-08-09 HTTP/1.1\" 200 -",
  "path": "/dashboard/2026-08-09",
  "method": "GET",
  "status": 200,
  "duration_ms": 12.3
}
```

Ship this file to Loki / Elastic / CloudWatch / whatever — the fields are
`path`, `method`, `status`, `duration_ms`, plus any `event` or `component`
added by pipeline code via `monitor.json_log.json_log()`.

## 4. Local dev quick-look

```bash
# terminal 1 — serve the dashboard
python webapp/server.py --port 8088

# terminal 2 — curl the metrics
curl -s localhost:8088/metrics | head -30

# terminal 3 — tail the JSONL access log
tail -f logs/web.jsonl | jq .
```

## 5. No extra dependencies

- Prometheus text exposition: hand-rolled in `monitor/metrics.py`
- JSONL logging: stdlib `logging` + `RotatingFileHandler` in `monitor/json_log.py`
- The dashboard is pure JSON — no templating, no plugins

If you need a different panel, edit `dashboard.json` and re-import.