# noaa-polymarket-research

Forecast snapshot tracker for Polymarket working-map weather locations.

## What it does
- Tracks all current working-map stations
- Fetches next-5-day forecast snapshots every run
- Stores daily max/min temperature forecasts in SQLite
- Keeps raw payloads for audit/debug
- Builds a local dashboard table by station + target date

## Sources in v1
- NOAA / NWS (`nws_noaa`) for U.S. stations
- GFS
- ECMWF
- ICON

## Main files
- `IMPLEMENTATION_PLAN.md` — approved implementation plan
- `scripts/run_once.py` — perform one collection run
- `scripts/serve.py` — serve local dashboard on `127.0.0.1:8765`
- `web/index.html` — generated dashboard
- `web/data.json` — generated dashboard dataset
- `data/forecast_tracker.sqlite` — local database

## Run manually
```bash
python3 scripts/run_once.py
python3 scripts/serve.py
```
