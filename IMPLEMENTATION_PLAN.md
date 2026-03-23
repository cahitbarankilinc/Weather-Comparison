# Forecast Snapshot System — Implementation Plan

Created: 2026-03-23
Project: `noaa-polymarket-research`

## Goal

Build a local system that continuously collects **forecast snapshots** for the current Polymarket working-map reference locations and saves them locally every **5 minutes**.

The system should let us inspect, for a chosen station + target date, a table like:

- station: `Toronto (CYYZ)`
- target date: `2026-03-25`
- rows: every collection time (e.g. `2026-03-23 15:30`, `15:35`, ...)
- columns: forecast models/sources
- values: **forecasted daily maximum temperature for the target date**, as known at the snapshot time

Example mental model:

Toronto (CYYZ): 25.03.2026
| snapshot time | NOAA | ICON | GFS | ECMWF | ... |
|---|---:|---:|---:|---:|---:|
| 23.03.2026 15:30 | 14.65 | 14.55 | 14.98 | 14.72 |
| 23.03.2026 15:35 | 14.35 | 14.65 | 14.68 | 14.66 |

The objective is not just “see latest forecast”, but **build a local time-series of how each model changed its view of the upcoming day**.

---

## What the system should do

## Core requirements

1. Track the existing Polymarket working-map station set
2. Fetch multiple forecast models/sources on a schedule
3. Recompute the **target day max temperature forecast** for each source/model
4. Save each snapshot locally
5. Serve a local UI/dashboard to inspect:
   - by station
   - by target date
   - by model/source
6. Keep the forecast horizon at **next 5 days** (rolling)

## Important design interpretation

At any snapshot time `T`, for each station, we need values for:
- `T+0 day`
- `T+1 day`
- `T+2 day`
- `T+3 day`
- `T+4 day`
- `T+5 day`

For each of those target days, we should derive the **daily max temperature** from the forecast returned by that source/model.

So each 5-minute run creates a small matrix:
- station × target_day × model → max_temp

---

## Recommended build strategy

## Recommendation: build in two phases

### Phase 1 — Stable, keyless backbone
Start with sources that can run **without asking you for paid API keys**.

Recommended initial model/source set:
- **NOAA/NWS** for U.S. stations only
- **GFS** (global)
- **ECMWF** (global, via accessible point wrapper or open-data-backed point source)
- **ICON** (global, via accessible point wrapper or open-data-backed point source)

Why this is the best first move:
- no dependency on waiting for external credentials
- gives immediate coverage for the whole working map
- lets us prove storage / UI / scheduling design first
- can later be extended with commercial consensus APIs without rewriting the core

### Phase 2 — Optional premium/vendor consensus layer
Add these only if you want a broader “provider consensus” view:
- Tomorrow.io
- OpenWeather
- Weatherbit
- optionally Windy API if you want it despite key/pro-plan friction

These are useful, but they should be treated as **extensions**, not as the foundation.

---

## Recommended source architecture

## Source families
We should distinguish between **model families** and **provider APIs**.

### A) Raw/official-ish model family layer
These represent real models we care about:
- `nws_noaa` (U.S.-only public forecast layer)
- `gfs`
- `ecmwf`
- `icon`

### B) Commercial/provider layer (optional later)
These are forecast vendors that may blend models / post-process data:
- `tomorrow`
- `openweather`
- `weatherbit`
- `windy`

## Important recommendation
For the UI and storage model, treat everything as a **forecast source** with fields:
- `source_id`
- `source_family` (`model`, `vendor`, `official_public`)
- `display_name`

That way, the table can later show:
- NOAA
- GFS
- ECMWF
- ICON
- Tomorrow
- OpenWeather
- Weatherbit
without changing the storage shape.

---

## Station scope

Use the current working map from `stations.json` / tracker mapping.

Initial station set:
- Toronto / CYYZ
- Atlanta / KATL
- Chicago / KORD
- Lucknow / VILK
- Ankara / LTAC
- Shanghai / ZSPD
- Seoul / RKSI
- London / EGLC
- Singapore / WSSS
- Dallas / KDAL
- Wellington / NZWN
- NYC / KLGA
- Paris / LFPG
- Munich / EDDM
- Seattle / KSEA
- Tel Aviv / LLBG
- Tokyo / RJTT
- Sao Paulo / SBGR
- Miami / KMIA
- Buenos Aires / SAEZ
- Taipei / RCSS

## Station metadata file
Create a canonical station registry file such as:
- `config/stations.json`

Each record should include:
- `city_label`
- `station_code`
- `latitude`
- `longitude`
- `country`
- `timezone`
- `resolution_source_url`
- `enabled`

### Important note
We still need to finalize **lat/lon and timezone** for every working-map station in a clean canonical file.
The codes are known, but the new system should not rely on scraped URL parsing at runtime.

---

## Storage design

## Main principle
Do **not** store only the latest values.
Store **immutable snapshots**.

## Recommended local database
Use **SQLite**.

Why:
- local
- robust
- easy querying
- easy aggregation for UI
- survives restarts
- no extra services required

## Recommended schema

### `stations`
- `station_code` (PK)
- `city_label`
- `lat`
- `lon`
- `timezone`
- `country`
- `resolution_source_url`

### `sources`
- `source_id` (PK)  e.g. `nws_noaa`, `gfs`, `ecmwf`, `icon`, `tomorrow`
- `display_name`
- `source_family`
- `enabled`
- `notes`

### `snapshot_runs`
Represents one scheduler execution.
- `run_id` (PK)
- `started_at_utc`
- `finished_at_utc`
- `status`
- `error_summary`

### `forecast_snapshots`
The main fact table.
- `id` (PK)
- `run_id`
- `snapshot_time_utc`
- `station_code`
- `source_id`
- `target_date_local`
- `target_timezone`
- `forecast_daily_max_c`
- `forecast_daily_min_c` (optional but recommended)
- `hour_count_used`
- `raw_payload_ref` (optional path/hash)
- `created_at_utc`

### `raw_payloads` (optional but highly recommended)
Save original API responses for audit/debug.
- `id`
- `run_id`
- `station_code`
- `source_id`
- `fetched_at_utc`
- `payload_path`
- `content_hash`
- `status_code`

## Why raw payload retention matters
If later we see a weird number in the table, we can verify:
- was it the provider’s actual output?
- was the max-temp derivation wrong?
- did the timezone conversion break?

This is extremely important for trust.

---

## File layout recommendation

Recommended new project structure inside `noaa-polymarket-research/`:

- `README.md`
- `IMPLEMENTATION_PLAN.md`
- `config/`
  - `stations.json`
  - `sources.json`
- `src/`
  - `forecast_tracker/`
    - `__init__.py`
    - `config.py`
    - `db.py`
    - `models.py`
    - `scheduler.py`
    - `derive.py`
    - `sources/`
      - `base.py`
      - `nws_noaa.py`
      - `gfs.py`
      - `ecmwf.py`
      - `icon.py`
      - `tomorrow.py`      (optional later)
      - `openweather.py`   (optional later)
      - `weatherbit.py`    (optional later)
    - `web/`
      - `app.py`
      - `templates/`
      - `static/`
- `data/`
  - `forecast_tracker.sqlite`
  - `raw_payloads/`
  - `logs/`
- `scripts/`
  - `run_once.py`
  - `backfill_recent.py`
  - `serve.py`

---

## Forecast derivation logic

## Core transformation
Most forecast sources return hourly values.
For each station + source + target_date:

1. Convert hourly timestamps into the station’s **local timezone**
2. Select only hours where local date == `target_date`
3. Compute:
   - `daily max temperature`
   - optionally `daily min temperature`
4. Save that as the snapshot fact

## Why this is the correct method
This keeps the system comparable even if different APIs expose data differently.
Instead of trusting a provider’s precomputed daily aggregate (which may use a different timezone/day-cut), we should prefer:
- derive daily max ourselves from hourly forecast values

This is especially important because Polymarket often resolves on local calendar day logic tied to the reference location.

---

## UI / dashboard plan

## Main page behavior
The local dashboard should support:

### Filters
- station selector
- target date selector
- source/model toggles
- optional time range selector for snapshot history

### Main table
For a given station + target date:

| snapshot time | NOAA | GFS | ECMWF | ICON | ... |
|---|---:|---:|---:|---:|---:|

### Extra views
Recommended extras:
1. **line chart** of each source’s max-temp forecast over time
2. **spread chart** showing max difference across models at each snapshot time
3. **latest snapshot card** for the next 5 days
4. **source health panel** showing fetch failures / stale data

## Very important UX recommendation
The dashboard should make it easy to switch among:
- `station → date view`
- `station → next 5 days summary`
- `date → all stations view`

Because eventually you’ll likely want both:
- “What happened to Toronto 25 March forecast over time?”
- “Across all stations, which target day is showing biggest model disagreement right now?”

---

## Scheduler plan

## Frequency
- every **5 minutes**

## Recommended mechanism
Because you prefer clear, reliable scheduling and this environment already prefers OpenClaw cron over OS-level `at`, there are two viable options:

### Option A — built-in loop process inside the app
- run a long-lived local process
- internal sleep loop every 5 minutes

### Option B — external scheduler triggers `run_once`
- OpenClaw cron calls a one-shot script every 5 minutes

## Recommendation
Use **Option A first** during development, then optionally add **Option B** for managed restarts.

Why:
- easier to debug
- easier to run manually
- less scheduler ambiguity during early development

Once stable, we can choose whether to wrap it in cron/launchd.

---

## Source selection recommendation

## Best initial source set
I recommend the first version ships with:

### 1. `nws_noaa`
- only for U.S. stations
- KLGA, KATL, KORD, KDAL, KSEA, KMIA, etc.
- keyless
- official
- simple

### 2. `gfs`
- global
- central backbone
- no vendor key needed if we use open paths / point wrapper approach
- strongest long-term research relevance

### 3. `ecmwf`
- global
- strong benchmark
- very valuable comparison model

### 4. `icon`
- global
- strong third-model comparison

## Why not start with vendor APIs first?
Because the system’s main risk is not “lack of sources”; it is:
- timezones
- day-cut correctness
- stable storage
- model/source normalization
- UI usability

Those should be solved before adding credential-heavy vendor APIs.

---

## Proposed implementation path

## Milestone 1 — planning and metadata
- create canonical station metadata with lat/lon/timezones
- define source registry
- set schema
- decide first source set

## Milestone 2 — local storage and run framework
- build SQLite schema
- add `run_once` pipeline
- add structured logging
- save raw payloads

## Milestone 3 — first sources
Implement these fetchers:
- `nws_noaa`
- `gfs`
- `ecmwf`
- `icon`

## Milestone 4 — derivation engine
- normalize hourly forecasts
- derive local-day max temp
- store next 5 target days for each snapshot

## Milestone 5 — local dashboard
- station + target date table
- latest/rolling view
- model lines chart

## Milestone 6 — reliability hardening
- retry logic
- stale-source detection
- source status panel
- retention and cleanup rules

## Milestone 7 — optional vendor expansion
- Tomorrow.io
- OpenWeather
- Weatherbit
- Windy (if you want to provide API credentials/plan)

---

## Recommended retention policy

Because 5-minute snapshots accumulate quickly:

### Snapshot math
For 21 stations × 4 sources × 6 target days × 288 runs/day:
that becomes large fairly quickly.

So we should keep:
- all snapshots in SQLite
- raw payload retention trimmed by policy, e.g.:
  - keep last 14 days of raw payloads in full
  - keep only hashed/audited summaries after that

We can also compress raw JSON.

---

## Error handling requirements

Each source fetch should record:
- success/failure
- HTTP status
- fetch duration
- parsing status
- whether target-day max could be derived

The UI should clearly show:
- missing value because source failed
- missing value because target date not in horizon
- missing value because provider returned incomplete data

These are different failure modes and should not be mixed.

---

## What I need from you (possibly)

## Not needed for first version
We can start **without any API key** if we stick to the recommended first version.

That means initial build can proceed with:
- NWS/NOAA (public)
- GFS
- ECMWF
- ICON

## Possibly needed later
If you want the consensus/vendor layer, then I may need:

### Optional credentials
- **Tomorrow.io API key**
- **OpenWeather API key / plan access**
- **Weatherbit API key**
- **Windy API key / plan**

## Metadata I may need from you if not already derivable
- confirmation that the current working-map station list is final for v1
- confirmation whether all temperatures should be stored/displayed in **°C** only
- confirmation whether local UI should prioritize:
  - station/date table first
  - or cross-station date comparison first

---

## Final recommendation

## Best path to build first
I recommend this exact first version:

### v1
- local SQLite-based system
- 5-minute polling loop
- sources:
  - `nws_noaa` (where available)
  - `gfs`
  - `ecmwf`
  - `icon`
- derive daily max from hourly forecast values
- save next 5 days for each station on every run
- local dashboard with station/date table + line chart

### Why this is the right v1
- no waiting for credentials
- gives the exact table structure you want
- covers the working map
- keeps the architecture expandable
- avoids vendor lock-in too early

---

## Questions to confirm before implementation

1. **Should v1 display temperatures only in °C?**
2. **Do you want all current working-map stations enabled by default, or should we start with a smaller subset (e.g. 5 stations) for faster stabilization?**
3. **Do you want vendor APIs (Tomorrow/OpenWeather/Weatherbit) included in v1 only if you provide keys now, or should I keep them for v2?**
4. **Do you want the system built inside this `noaa-polymarket-research` project, or promoted into a more productized standalone app directory once you approve?**

---

## Approval checkpoint

Do **not** start implementation until this plan is approved.
Once approved, the next step is:
- create canonical station metadata
- scaffold the project structure
- implement the first fetch/storage pipeline
