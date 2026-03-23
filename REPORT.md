# NOAA × Polymarket Weather Research

Created: 2026-03-23

## Scope

This project answers four questions:

1. Which **official NOAA / NWS APIs and data products** are useful for Polymarket weather markets?
2. Can we access **past forecasts** (not just observations) so we can compare forecast-vs-outcome using our existing data?
3. Does NOAA forecast the **actual reference locations** Polymarket uses (airport/station-level), not just the city label?
4. Which parts of the current Polymarket location set are covered **directly** by NWS point APIs vs only **indirectly** through global model data?

---

## Executive summary

### Short answer

- **Yes, NOAA is useful**, but it splits into **two very different layers**:
  1. **NWS API (`api.weather.gov`)** → easy, direct, point/grid forecasts, but effectively **U.S.-only / NWS-area only**.
  2. **NOAA global model data (mainly GFS via NOMADS / NCEI)** → covers the **whole globe**, including many Polymarket airport references, but it is **raw model data**, not a simple city forecast API.

- **Yes, past forecasts are available**, but not in one neat consumer endpoint.
  - For U.S. point forecasts, there does **not** appear to be a simple official “give me last week’s hourly point forecast JSON” endpoint like `api.weather.gov/forecast/archive/...`.
  - However, **historical NOAA forecast runs are available through GFS archives** (NCEI / NOMADS / THREDDS / HTTPS/HAS), which means we can reconstruct what NOAA predicted at earlier times.

- For the current Polymarket resolution locations in the repo:
  - **Direct NWS API coverage** exists for the U.S. airports/cities in our set.
  - **Non-U.S. locations are not covered by `api.weather.gov/points/...`**.
  - But many of those same non-U.S. airport references are still covered by **global NOAA model output (GFS)**.

### Bottom line for implementation

The best NOAA architecture is:

- **Use `api.weather.gov` for U.S. reference locations** (KLGA, KATL, KORD, KDAL, KSEA, KMIA, etc.)
- **Use archived/current GFS model data for non-U.S. reference locations** (LTAC, EGLC, RKSI, SAEZ, LFPG, SBGR, ZSPD, etc.)
- Keep **Weather.com / Wunderground / resolution-source pages** as the observed-truth / settlement-verification layer

That gives a clean split:

- **forecast alpha** → NOAA/NWS
- **observed settlement truth** → existing Weather.com / Wunderground stack

---

## Existing Polymarket reference-location map found in current projects

From `polymarket-weather-scanner/src/polymarket_weather_scanner/tracker.py` the current working city → resolution-source mapping is:

| Polymarket label | Reference code | Reference source in repo |
|---|---:|---|
| Toronto | CYYZ | Mississauga / Toronto Pearson |
| Atlanta | KATL | Atlanta airport |
| Chicago | KORD | Chicago O'Hare |
| Lucknow | VILK | Lucknow airport |
| Ankara | LTAC | Çubuk / Esenboğa |
| Shanghai | ZSPD | Shanghai Pudong |
| Seoul | RKSI | Incheon |
| London | EGLC | London City |
| Singapore | WSSS | Changi |
| Dallas | KDAL | Dallas Love Field |
| Wellington | NZWN | Wellington |
| NYC | KLGA | LaGuardia |
| Paris | LFPG | Charles de Gaulle |
| Munich | EDDM | Munich airport |
| Seattle | KSEA | Sea-Tac |
| Tel Aviv | LLBG | Ben Gurion |
| Tokyo | RJTT | Haneda |
| Sao Paulo | SBGR | Guarulhos |
| Miami | KMIA | Miami |
| Buenos Aires | SAEZ | Ezeiza |
| Taipei | RCSS | Taipei Songshan |

Important existing project note: Polymarket’s city labels often map to **airport/station locations**, not downtown city centers. Example already known in the repo: **Ankara → LTAC / Esenboğa area**, not generic Ankara-center weather.

---

## What NOAA/NWS products are actually relevant?

## 1) NWS API (`api.weather.gov`) — easiest operational API

Official docs show:
- free/open data
- machine-readable JSON
- `/points/{lat},{lon}` lookup
- `forecast` and `forecastHourly` discovery from the returned gridpoint
- hourly and 12-hour forecast products

Useful endpoints:

- `https://api.weather.gov/points/{lat},{lon}`
- `https://api.weather.gov/gridpoints/{office}/{x},{y}/forecast`
- `https://api.weather.gov/gridpoints/{office}/{x},{y}/forecast/hourly`
- `https://api.weather.gov/gridpoints/{office}/{x},{y}` (raw grid data / numeric fields)
- Alerts endpoints if ever needed

Why it matters for Polymarket:
- easy integration
- official NWS forecast, not scraped UI
- hourly product available
- can resolve airport-adjacent U.S. locations by coordinates instead of city-name guessing

### What it does **not** solve
- not a world forecast API
- not a neat historical point-forecast archive API
- outside NWS forecast domain it returns no data

---

## 2) NWS Gridpoint data — better than just the pretty forecast text

The point endpoint is mainly a discovery layer.
Once we have a valid U.S. point, the returned properties expose:
- forecast office
- grid id
- grid x/y
- hourly forecast endpoint
- forecast endpoint

This matters because Polymarket temperature buckets need more than a human-readable sentence. Gridpoint products are much more suitable for automation than consumer-facing pages.

---

## 3) NOAA GFS via NOMADS — global forecast layer

Official NOAA/NCEP NOMADS pages list:
- GFS 0.25°, 0.5°, 1.0°
- 6-hour model cycles
- global model datasets
- grib filter / HTTPS access

NCEI’s GFS page confirms:
- GFS is a **global model**
- 4 model cycles/day: **00, 06, 12, 18 UTC**
- forecasts extend out to as much as **16 days** depending on product/resolution
- historical forecast archives exist

This is the NOAA path that can cover:
- LTAC (Ankara / Esenboğa)
- EGLC (London City)
- RKSI (Incheon)
- SAEZ (Ezeiza)
- LFPG, SBGR, ZSPD, WSSS, etc.

### Practical downside

This is not as plug-and-play as `api.weather.gov`.
You generally need to:
- know the station coordinates
- query a gridded model source
- interpolate or nearest-gridpoint sample
- derive forecast highs / hourly temps yourself

So it is powerful, but much more “research/data-engineering” than “simple API call”.

---

## 4) GFS MOS / LAMP — airport/station-flavored guidance, but mostly U.S.-centric

Useful because Polymarket often resolves against airport-like locations.

### GFS MOS
Official NOAA MDL docs say:
- station-based MOS provides guidance at **meteorological station locations such as airports**
- includes variables like temperature, precipitation, etc.
- coverage is mainly **CONUS, Alaska, Hawaii, Puerto Rico, USVI**, with limited extras and select Canadian stations

### LAMP
Official NOAA MDL docs say:
- station guidance for **2000+ stations**
- hourly updates for many elements
- includes temperature, POP, wind, visibility, etc.
- aviation/station-oriented

### Why this matters
If our target is **U.S. airport-like references** such as KLGA/KATL/KORD/KSEA/KMIA/KDAL, MOS/LAMP may be a very good fit because they are already station-oriented instead of city-oriented.

### Why it is not the universal answer
- not global in the way GFS is global
- product structure is more legacy/text/bulletin-oriented
- likely better as an advanced U.S.-only enhancement than as the first global NOAA integration layer

---

## Can we see NOAA’s past forecasts?

## Short answer: **yes, but mostly through model archives, not a simple point-history API**

### What appears available

#### A) Historical GFS forecast archives
NCEI’s GFS page explicitly lists forecast archives with period-of-records and access methods:
- HTTPS
- THREDDS / TDS
- HAS
- multi-year period of record depending on resolution/product

This is the most important finding for backtesting.

It means we should be able to ask questions like:
- “What did NOAA’s GFS 24h-before-run predict for LTAC on 2026-02-15?”
- “How did NOAA forecast KLGA’s daily high 12h / 24h / 36h before expiry?”
- “How did forecast error compare to Polymarket pricing at those times?”

#### B) Current / recent NOMADS operational archives
NOMADS provides operational model access and short trailing windows.
This is useful for near-real-time ingestion and recent-run comparisons.

#### C) MOS station archives / station lists
The MOS station archive pages and product pages indicate historical/station archival structure exists for at least some station-oriented guidance products.
But this looks more cumbersome and U.S.-focused than GFS archive usage.

### What does **not** appear readily available

A simple official endpoint like:
- `api.weather.gov/points/{lat},{lon}/forecast/archive?...`

I did not find evidence of a clean official public NWS point-forecast archive endpoint equivalent to the live JSON point forecast service.

So for **historical backtesting**, the realistic NOAA path is:

1. store or reconstruct the relevant airport coordinates
2. fetch archived **GFS run data**
3. extract the needed temperature field for the target point/time
4. compare to:
   - Polymarket bucket prices / explicit chart windows
   - final observed weather from current truth stack

---

## Coverage check against actual reference locations

I ran direct tests against `api.weather.gov/points/{lat},{lon}` using approximate coordinates for known reference airports/stations.

### Result

#### U.S. reference airports: works
- **KLGA** → success
- **KATL** → success

The API returned live NWS gridpoint forecast endpoints for both.

#### Non-U.S. reference airports/stations: fails on direct NWS point API
- **LTAC** → 404 `Data Unavailable For Requested Point`
- **EGLC** → 404
- **RKSI** → 404
- **SAEZ** → 404

This is the single most important operational result in this project.

### Meaning

- For **U.S. Polymarket reference locations**, NOAA/NWS offers a direct, easy API path.
- For **non-U.S. Polymarket reference locations**, NOAA still matters — but through **global model products like GFS**, not through the simple NWS point API.

---

## Practical coverage classification for the current location set

## Direct `api.weather.gov` candidates (strong fit)

These are U.S. reference locations and should be first priority for direct NOAA/NWS integration:

- KLGA (NYC)
- KATL (Atlanta)
- KORD (Chicago)
- KDAL (Dallas)
- KSEA (Seattle)
- KMIA (Miami)
- Possibly U.S. territories later if ever needed

## Maybe via station/MOS enhancement (mostly U.S.)

Good candidates for later NOAA station-guidance work:
- KLGA
n- KATL
- KORD
- KDAL
- KSEA
- KMIA
- CYYZ maybe partial / special-case Canadian support in some MOS products

## Global NOAA path required (not `api.weather.gov`)

These should be treated as **GFS/NOMADS/NCEI-only NOAA cases**:
- LTAC (Ankara / Esenboğa)
- EGLC (London City)
- RKSI (Incheon)
- SAEZ (Ezeiza)
- LFPG (Paris CDG)
- SBGR (São Paulo Guarulhos)
- ZSPD (Shanghai Pudong)
- WSSS (Singapore Changi)
- NZWN (Wellington)
- LLBG (Tel Aviv)
- RJTT (Tokyo Haneda)
- EDDM (Munich)
- RCSS (Taipei Songshan)
- VILK (Lucknow)

---

## Recommended build order

## Phase 1 — U.S. direct NOAA integration

Goal: fastest path to value.

Build a small fetcher that:
1. maps the Polymarket reference airport to coordinates
2. calls `api.weather.gov/points/{lat},{lon}`
3. resolves to `forecastHourly`
4. stores hourly forecast snapshots by run time / fetched time

Use this first for:
- KLGA
- KATL
- KORD
- KDAL
- KSEA
- KMIA

Why first:
- easy JSON
- no GRIB parsing
- directly testable against current Polymarket US markets

## Phase 2 — archived NOAA forecast backtest layer

Goal: answer “what did NOAA think before settlement?”

Build a research fetcher around archived GFS runs from:
- NCEI GFS archives
- optionally NOMADS trailing operational window for recent days

Minimum target capability:
- given reference airport coords + forecast run time + target day
- extract predicted near-surface temperature / hourly surface temperature
- compute forecasted daily max or expiry-window expectation

This is the key layer for forecast-vs-market backtesting.

## Phase 3 — global airport coverage

Goal: extend NOAA forecast research beyond U.S. markets.

Prioritize high-value non-U.S. Polymarket locations:
1. EGLC (London)
2. LTAC (Ankara)
3. RKSI (Seoul)
4. SAEZ (Buenos Aires)
5. LFPG / SBGR / ZSPD

This should use GFS point extraction, not `api.weather.gov`.

## Phase 4 — optional station-oriented U.S. refinement

Explore whether station-based NOAA guidance improves edge for U.S. airport markets:
- GFS MOS
- LAMP

This may be especially useful for short-horizon temperature/high-temp markets if the airport/station framing matters more than generic public forecast text.

---

## What I would build next in this new project

### Minimal first deliverables

1. `stations.csv` / `stations.json`
   - city label
   - airport/station code
   - source URL
   - country
   - NOAA direct API support (`yes/no`)
   - NOAA global-model support (`yes`)

2. `noaa_capabilities.md`
   - NWS live API
   - GFS archive access options
   - MOS/LAMP notes

3. `us_nws_probe.py`
   - probes `api.weather.gov/points` for U.S. reference airports
   - stores returned forecast/gridpoint URLs

4. `global_gfs_research.md`
   - notes on best access path for archived global point forecasts
   - especially for LTAC / EGLC / RKSI / SAEZ

### Most important research question to answer next

> Can we reliably extract **daily-high forecast values** for airport coordinates from archived GFS runs at specific lead times (e.g. T-36h, T-24h, T-12h)?

If the answer is yes, then we can compare:
- NOAA forecast distribution / central estimate
- Polymarket bucket probabilities near the same time
- final observed resolved temperature

That would be the cleanest NOAA-vs-market backtest path.

---

## Key conclusions

1. **NOAA is usable, but not one thing**:
   - NWS API for direct U.S. points
   - GFS archives for global/historical work

2. **Past forecasts are available enough for research**, mainly through archived GFS model runs.

3. **Polymarket’s real reference locations matter** more than city labels.
   - Example already validated in project context: **Ankara → LTAC / Esenboğa-area station**, not generic Ankara center.

4. **`api.weather.gov` is not a global solution**.
   - It works for KLGA/KATL-like points
   - It does not work for LTAC/EGLC/RKSI/SAEZ-like points

5. For this project, the best split is:
   - **U.S. markets** → direct NWS API first
   - **non-U.S. markets** → archived/current GFS extraction
   - **truth/settlement** → keep current Weather.com/Wunderground observation stack

---

## Source notes used in this report

Project-internal:
- `polymarket-weather-scanner/src/polymarket_weather_scanner/tracker.py`
- prior PolyTrader notes showing city labels often map to airport/station resolution pages

External official NOAA/NWS references checked:
- NWS API documentation: `weather.gov/documentation/services-web-api`
- NCEI GFS page: `ncei.noaa.gov/products/weather-climate-models/global-forecast`
- NOMADS catalog: `nomads.ncep.noaa.gov`
- NOAA MDL GFS MOS page: `vlab.noaa.gov/web/mdl/gfs-mos`
- NOAA MDL LAMP page: `vlab.noaa.gov/web/mdl/lamp`
- NOAA MDL MEX page: `vlab.noaa.gov/web/mdl/mex-card`
- NOAA MDL MOS stations archive: `vlab.noaa.gov/web/mdl/mos-stations-archive`
