# Geo-Macro Risk Agent

A lightweight alerting system for Indian options sellers. It watches three geopolitical zones
(Strait of Hormuz, Red Sea / Gulf of Aden, India-Pakistan border), correlates independent signals,
scores volatility and gap risk per region, and sends an alert before you take a NIFTY iron condor decision.

It does **not** predict NIFTY direction and does **not** trade. It answers one question:
*is global event risk elevated enough to change how I size or place weekly option-selling positions?*

All data is live and public. Nothing is simulated or seeded. When a feed has nothing to report the
agent says so, and when a feed is down it shows it on the health panel instead of guessing.

## What it watches (spec section 2)

| Signal | Real source | Key needed |
|---|---|---|
| GPS degradation cluster (proxy for jamming) | ADS-B navigation accuracy (NACp) from adsb.lol, fallback adsb.fi. Same technique GPSJam and ShadowBroker use. | none |
| Military aircraft spike | adsb.lol / adsb.fi military feed, filtered to each zone | none |
| Tanker / AIS dark activity | aisstream.io websocket: dark gaps, stationary tankers, identity changes inside chokepoints | free key |
| Conflict news velocity | GDELT DOC 2.0 (region + conflict keywords) | none |
| Crude confirmation | Brent (WTI fallback) from Yahoo Finance | none |
| India VIX confirmation | Yahoo Finance, fallback NSE | none |
| ShadowBroker (optional) | your self-hosted backend, `SHADOWBROKER_API_BASE` | none |

## How scoring works (spec sections 6-8)

* Each extractor fires on the spec thresholds (config.yaml) and stores a signal with evidence.
* A region score is the sum of active signal weights times the region multiplier, capped at 100.
  Hormuz x1.25, Red Sea x1.10, India-Pak x1.30. Bands: 0-30 NORMAL, 31-55 CAUTION, 56-75 HIGH, 76-100 AVOID.
* Signals stay active for 2 hours (news for 4 hours).
* Independence rule: crude and VIX only count when at least one OSINT signal is active in the region. An alert needs 2 or more independent signal types.
* Alerts: the same region and band is not repeated within 60 minutes, a higher band sends immediately, and a drop to NORMAL for 3 checks after HIGH/AVOID sends a cooldown message. A morning summary goes out at 08:45 IST on trading days.
* Every alert stores its snapshot, signals and raw evidence. Click an alert on the dashboard, or `GET /alerts/{id}`, to see why it fired.

Two small choices beyond the spec, both in config.yaml: the "average severity >= 0.65" GPS rule needs at least 3 aircraft (stops one faulty avionics unit from raising a signal), and market readings older than 45 minutes count as stale (market closed) and give no signal.

## Run locally

```
python -m venv venv
venv\Scripts\activate          (Windows)   |   source venv/bin/activate   (Mac/Linux)
pip install -r requirements.txt
copy .env.example .env         (Mac/Linux: cp .env.example .env)
python -m app.main
```
Open http://127.0.0.1:8080. With no `DATABASE_URL` it uses a local SQLite file. The first scoring run happens about 75 seconds after start, and ADS-B needs about 90 seconds per cycle because it queries about 22 map tiles politely.

Tests: `pytest -q`

## Deploy on Render (free)

1. Push this folder to a GitHub repo.
2. Render > New > Blueprint > pick the repo. It reads `render.yaml` and creates the web service. It asks you for the secret values.
3. When Render asks, fill `DATABASE_URL` (Neon string, step 4) and `ADMIN_PASSWORD` (any strong password you choose). Later, in the Environment tab, optionally add `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `AISSTREAM_API_KEY`.
4. Use a free Neon Postgres for history: create a project at neon.tech, copy the connection string and set it as `DATABASE_URL` in Render . Without a durable Postgres, history, alerts and your edited settings are lost when the service restarts.

**Render free-tier limits (be aware before the demo)** (source: https://render.com/docs/free)

* The 750 free instance hours are shared across the whole workspace.
* A free service can be restarted at any time, and spins down after 15 minutes without inbound traffic, which pauses the scheduler until the next visit.
* Local files, including SQLite, are lost on every restart or redeploy. SQLite is for local demos only.
* Heavy service-initiated traffic can get a free service suspended. The app keeps its outbound polling polite (about 0.6 requests per second at most).
* An UptimeRobot ping on `/health` helps the service wake up but is not an always-on guarantee. For continuous monitoring use a paid always-on instance.
* Render's own free Postgres expires after 30 days; use Neon for something permanent.

Docker: `docker compose up --build` runs the app with Postgres.

## Telegram

1. In Telegram open @BotFather, send `/newbot`, copy the token into `TELEGRAM_BOT_TOKEN`.
2. Open your new bot, press Start, send "hi".
3. Run `python scripts/telegram_chat_id.py`, copy the id into `TELEGRAM_CHAT_ID`.
4. Check it works: `POST /alerts/test` (rate limited to one per 30 seconds).

Without Telegram, alerts are still stored and shown on the dashboard with status `logged`.

## API (spec section 11 plus extras)

`GET /health` `GET /risk/latest` `GET /risk/region/{region}` `GET /alerts/recent` `POST /alerts/test`
Extras: `GET /alerts/{id}` (evidence), `POST /feedback` (useful, false_positive, too_late, missed_event),
`GET /signals/recent`, `GET /feeds/status`, `GET /alerts.csv`, `GET /api/overview`, `GET /api/map`, dashboard at `/`.
Set `ADMIN_TOKEN` to require an `X-Admin-Token` header on POST routes.

## Layout

```
app/collectors/   adsb, gdelt, market, ais, shadowbroker
app/extractors.py six signal extractors      app/scoring.py correlation + risk score
app/alerts.py     dedupe, Telegram, LLM note app/pipeline.py scheduler jobs
app/main.py       FastAPI + dashboard         config.yaml thresholds, weights, regions
tests/            scoring, rules, alerts, AIS logic, API
```

## Known limits (honest)

* ADS-B GPS degradation is a proxy for jamming, not a direct measurement. Coverage depends on volunteer receivers, so the feed shows less in some areas than is really there.
* "0 military aircraft" means none are visible in the public feed. It does not mean none are present, and the app never claims any aircraft has its transponder off. Feed visibility and real-world absence are different things.
* AIS from aisstream.io is terrestrial. A vessel going quiet can be a coverage edge, so the tanker signal needs 3 anomalies in 2 hours.
* GDELT is rate limited (one request per 5 seconds, shared); the collector throttles and retries.
* Yahoo Finance is unofficial. VIX only updates 09:15-15:30 IST.
* No backtesting (out of scope in the spec). Use the feedback endpoint to log which alerts were useful.

## Spec coverage notes
- **Test case 2** in the spec ("news spike alone in Red Sea = CAUTION") contradicts the spec's own formula (15 x 1.10 = 16.5 = NORMAL, and one signal family never alerts). The app follows the formula. CAUTION needs news plus a military spike (35 x 1.1 = 38.5).
- **Manual test cases 1-4**: `python scripts/inject_test_events.py` runs them on a throwaway SQLite DB. It refuses to run against a `DATABASE_URL` unless you pass `--force`. The live app never uses injected data.
- **Stale feeds**: if GPS/aircraft or AIS has no successful run for 30 minutes, a "system warning" alert is created (max one per feed per 2 hours) and sent to Telegram.
- **Telegram**: 3 attempts, then the alert is saved with status `failed`.
- **Logging**: `LOG_LEVEL` env. Logs signals generated, alerts sent or skipped with reason, and LLM fallback.
- Frontend, strike backtest and overnight gap-risk page are outside the spec MVP; they are extras built on real Yahoo history.
- **Map tiles**: the Live map uses Esri's free World Dark/Light Gray basemap (English labels, attribution shown). Free tiles are for light use. For heavy production traffic, switch to a map provider key (MapTiler, Stadia) in `app/static/app.js` (`L.tileLayer`).
- **Risk now vs usual** (Overview): the percentile uses only this agent's own stored snapshots. It needs at least 100 readings over 24 hours, and until then the page says it is still building a baseline instead of showing a number.
- **Motion**: page transitions, count-ups and chart reveals are CSS/JS only and are switched off by `prefers-reduced-motion`.
