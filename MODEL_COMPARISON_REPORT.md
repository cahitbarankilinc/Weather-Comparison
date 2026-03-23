# ECMWF vs GFS vs ICON for Polymarket Working Map

Created: 2026-03-23

## Goal

Evaluate three forecast-model families for the current Polymarket working map:

- **ECMWF** (European Centre for Medium-Range Weather Forecasts)
- **GFS** (NOAA/NCEP)
- **ICON** (DWD / Deutscher Wetterdienst)

The research answers two separate questions:

1. **Official access**: how can these models actually be fetched programmatically?
2. **Practical point availability**: do they return forecast data for our current Polymarket reference locations?

---

## Executive summary

### Short answer

- **All three model families are usable for Polymarket-style point forecasting.**
- For **official direct access**, they are not equally convenient:
  - **GFS**: easiest official raw-data access for automation (NOMADS + GFS archives)
  - **ECMWF**: official open data exists, but it is a rolling archive and mostly GRIB-oriented; full history is not as open/simple
  - **ICON**: official DWD open data exists, but also GRIB-oriented and less point-API-friendly than a consumer JSON API
- For **practical point testing across our working map**, all three worked on almost all tested airport/reference locations when queried through a model-selectable point API wrapper.

### Best interpretation for our project

- If we want the **most operationally convenient official research path**, **GFS** is still the strongest base model.
- If we care about the model with the strongest reputation for raw forecast skill, **ECMWF is still the prestige choice**, but official historical access is more constrained than GFS.
- If we want another serious global model to compare against GFS/ECMWF, **ICON is absolutely viable**, and its official DWD open data is real — just not a neat point JSON API by default.

---

## Important methodology note

There are **two different access layers** here:

### A) Official model-provider access
This means the model owner’s own distribution path:
- ECMWF open data / web API / cloud mirrors
- NOAA NOMADS / NCEI for GFS
- DWD Open Data for ICON

These are mostly **GRIB / raw model data** interfaces.

### B) Practical point API testing
To answer “does this model work for our reference airports?” in a fast, location-by-location way, I also tested a **model-selectable point forecast API wrapper** (`open-meteo`) that exposes:
- `ecmwf_ifs`
- `gfs_global`
- `icon_global`

This second layer is not the official model archive itself, but it is useful to test **actual point forecast availability** across our current working map.

So:
- **official access** answers whether the model is obtainable at source
- **point wrapper tests** answers whether it works for our locations in practice

---

## Official access findings

## 1) ECMWF

### What I found
Official ECMWF pages confirm:
- ECMWF provides **Open Data**
- this is a **subset** of real-time IFS / AIFS products
- products are available at **0.25° resolution** in **GRIB2**
- data retention is a **rolling archive of the most recent 12 forecast runs** (roughly 2–3 days)
- for broader or historical access, ECMWF points users toward agreements / broader archive products
- cloud mirrors exist (AWS / Azure / GCP)

### Meaning for us
ECMWF is real and fetchable, but the official open-data path is:
- good for **real-time / near-real-time forecast ingestion**
- **not ideal for long historical backtesting** unless we use a paid/extended route or an external retained copy

### Practical implication
If we build ECMWF into the stack:
- great for current-run forecast comparison
- weaker than GFS for simple cheap historical archive research

---

## 2) GFS

### What I found
Official NOAA/NCEP/NCEI pages confirm:
- GFS official access is available through **NOMADS**
- raw subsets can be scripted with **GRIB Filter**
- current operational model products are distributed on 00 / 06 / 12 / 18 UTC cycles
- NCEI provides **historical GFS forecast archives**
- official access methods include HTTPS / THREDDS / HAS depending on product and period

### Meaning for us
GFS remains the most research-friendly official source for our use case because it offers:
- global coverage
- strong current access
- real archive story for past runs
- decent scripting surface for automation

### Practical implication
If the question is:
> “Which model should we first use for past-forecast-vs-Polymarket backtests?”

My answer is still:
- **GFS first**

because the official archive path is the clearest.

---

## 3) ICON

### What I found
Official DWD pages confirm:
- DWD runs **ICON global** and nested regional ICON models
- forecast data are distributed in **GRIB2**
- official free access is through **DWD Open Data**
- ICON global is **global coverage**
- 00 / 06 / 12 / 18 UTC cycles
- forecast horizon is up to **+180h** for 00/12 and **+120h** for 06/18
- regional nests exist for Europe and Germany, but the global ICON is the relevant one for our worldwide Polymarket set

### Meaning for us
ICON is absolutely real and usable, but like ECMWF/GFS official raw access, it is not a clean airport JSON point API by default.

### Practical implication
ICON is best viewed as:
- a strong additional global comparison model
- especially useful when we want consensus / disagreement checks versus GFS and ECMWF

---

## Working-map reference locations used

The current project mapping includes airport/station-like references such as:

- CYYZ
- KATL
- KORD
- VILK
- LTAC
- ZSPD
- RKSI
- EGLC
- WSSS
- KDAL
- NZWN
- KLGA
- LFPG
- EDDM
- KSEA
- LLBG
- RJTT
- SBGR
- KMIA
- SAEZ
- RCSS

These correspond to the actual Polymarket resolution-style locations in the repo, not generic city centers.

---

## Actual API availability tests by location

I ran live point forecast requests for the station coordinates using model-selectable API queries for:
- **ECMWF** via `ecmwf_ifs`
- **GFS** via `gfs_global`
- **ICON** via `icon_global`

The probe requested hourly `temperature_2m` for each location.

## Result summary

### ECMWF
- Worked for **all tested working-map locations**

### GFS
- Worked for **all tested working-map locations**

### ICON
- Worked for **all tested working-map locations except one transient failure**
- **LLBG** returned a timeout once during the run
- This looks more like a request/transient issue than a true model-coverage limitation, because ICON succeeded for other nearby and distant global points in the same batch

### Practical conclusion
For our working map, **all three models are operationally usable as global point forecast sources**.

---

## Coverage interpretation by model

## ECMWF
### Strengths
- strongest reputation for medium-range forecast quality
- global
- usable for all current Polymarket airport-like locations in practical tests

### Weaknesses
- official open historical access is not as friendly as GFS
- open-data archive is rolling / short-lived
- raw-data workflow is heavier

### Best use in our project
- top-tier comparison model
- current/near-term forecast edge validation
- consensus model against GFS and ICON

---

## GFS
### Strengths
- official access is the easiest to automate seriously
- strong global coverage
- best official archive story for backtests
- worked for all tested working-map locations

### Weaknesses
- lower prestige than ECMWF in raw “most accurate model” discourse
- raw data still needs extraction/interpolation work

### Best use in our project
- **primary historical forecast research model**
- first-choice official model for backtesting Polymarket edges

---

## ICON
### Strengths
- official global model from DWD
- official open-data access exists
- worked for almost all tested points, with only one transient timeout in the batch
- useful as an independent non-US, non-ECMWF comparison model

### Weaknesses
- official point access less straightforward than a simple JSON API
- regional submodels are great in Europe but not globally relevant to every Polymarket location
- historical workflow less obvious than GFS

### Best use in our project
- third-model cross-check
- especially useful for Europe-adjacent and global consistency checks
- model disagreement detector alongside ECMWF and GFS

---

## What this means for the trading/research stack

If the goal is **one best model to start with**:
- start with **GFS**

If the goal is **best forecast reputation**:
- ECMWF is the premium benchmark

If the goal is **multi-model edge detection**:
- use all three:
  - ECMWF
  - GFS
  - ICON

The best practical architecture is probably:

1. **GFS** as the main official historical-research backbone
2. **ECMWF** as the prestige comparison model for live/near-live forecasts
3. **ICON** as the independent third vote / disagreement detector

That gives us model spreads like:
- GFS vs ECMWF disagreement
- ICON confirmation or rejection
- then compare the spread against Polymarket pricing

This is much more interesting than betting on one model in isolation.

---

## Direct answer to “hangi working map’ler için çalışıyorlar?”

For the current Polymarket working map in the repo:

- **ECMWF**: effectively works for **all tested reference locations**
- **GFS**: effectively works for **all tested reference locations**
- **ICON**: effectively works for **all tested reference locations**, with **one transient timeout on LLBG** during this run

So the honest answer is:

> **Bu üçü de working map’imizin neredeyse tamamı için kullanılabilir görünüyor.**

The real difference is **not coverage**.
The real difference is:
- forecast quality/reputation
- ease of official access
- historical archive convenience

---

## My recommendation

### If you want the next practical step:
Build a **3-model comparison probe** for the current working map:
- fetch point forecasts for each reference airport
- normalize to the same target day / local day window
- compare daily high / hourly temperature tracks
- record divergence vs Polymarket bucket prices

### If you want the most useful first implementation:
1. **GFS first** (best official archive / research path)
2. add **ECMWF** next
3. add **ICON** as third-model confirmation

That order gives the highest research value per engineering effort.

---

## Sources checked

Official / near-official:
- ECMWF Open Data: `https://www.ecmwf.int/en/forecasts/datasets/open-data`
- ECMWF access docs / open-data references
- DWD NWP forecast data: `https://www.dwd.de/EN/ourservices/nwp_forecast_data/nwp_forecast_data.html`
- DWD Open Data references
- NOAA/NCEP NOMADS and GFS docs
- NOAA/NCEI GFS archive pages

Practical live point tests:
- model-selectable forecast API wrapper using:
  - `ecmwf_ifs`
  - `gfs_global`
  - `icon_global`

---

## Final takeaway

If the question is “Which one actually works for our locations?” then the answer is:
- **all three**

If the question is “Which one should we build around first?” then the answer is:
- **GFS for archive/backtest infrastructure**
- **ECMWF for premium benchmark comparisons**
- **ICON for third-model confirmation**
