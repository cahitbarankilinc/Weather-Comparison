from __future__ import annotations

import hashlib
import json
import sqlite3
import traceback
from datetime import datetime, timezone
from pathlib import Path

from .config import DB_PATH, RAW_PAYLOAD_DIR, WEB_DIR, load_sources, load_stations
from .db import connect
from .derive import summarize_hourly_maxes
from .sources.nws_noaa import fetch_nws
from .sources.open_meteo import fetch_open_meteo


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dirs() -> None:
    RAW_PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def upsert_metadata(conn: sqlite3.Connection) -> None:
    for station in load_stations():
        conn.execute(
            '''INSERT INTO stations(station_code, city_label, lat, lon, timezone, country, resolution_source_url)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(station_code) DO UPDATE SET
                 city_label=excluded.city_label,
                 lat=excluded.lat,
                 lon=excluded.lon,
                 timezone=excluded.timezone,
                 country=excluded.country,
                 resolution_source_url=excluded.resolution_source_url''',
            (station.station_code, station.city_label, station.latitude, station.longitude, station.timezone, station.country, station.resolution_source_url),
        )
    for source in load_sources():
        conn.execute(
            '''INSERT INTO sources(source_id, display_name, source_family, notes)
               VALUES(?,?,?,?)
               ON CONFLICT(source_id) DO UPDATE SET
                 display_name=excluded.display_name,
                 source_family=excluded.source_family,
                 notes=excluded.notes''',
            (source.source_id, source.display_name, source.source_family, source.notes),
        )
    conn.commit()


def write_raw_payload(run_id: int, station_code: str, source_id: str, payload: dict, status_code: int | None, fetched_at: str, conn: sqlite3.Connection) -> None:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')
    digest = hashlib.sha256(raw).hexdigest()
    payload_dir = RAW_PAYLOAD_DIR / station_code / source_id
    payload_dir.mkdir(parents=True, exist_ok=True)
    payload_path = payload_dir / f'{fetched_at.replace(":", "-")}.json'
    payload_path.write_bytes(raw)
    conn.execute(
        '''INSERT INTO raw_payloads(run_id, station_code, source_id, fetched_at_utc, payload_path, status_code, content_hash)
           VALUES(?,?,?,?,?,?,?)''',
        (run_id, station_code, source_id, fetched_at, str(payload_path.relative_to(DB_PATH.parent.parent)), status_code, digest),
    )


def fetch_source(source_id: str, lat: float, lon: float, country: str):
    if source_id == 'nws_noaa':
        if country != 'US':
            return None
        return fetch_nws(lat, lon)
    if source_id in {'gfs', 'ecmwf', 'icon'}:
        return fetch_open_meteo(source_id, lat, lon)
    raise ValueError(f'Unsupported source_id: {source_id}')


def build_dashboard_json(conn: sqlite3.Connection) -> None:
    stations = [dict(row) for row in conn.execute('SELECT * FROM stations ORDER BY city_label')]
    sources = [dict(row) for row in conn.execute('SELECT * FROM sources ORDER BY display_name')]
    rows = [dict(row) for row in conn.execute(
        '''SELECT fs.snapshot_time_utc, fs.station_code, fs.source_id, fs.target_date_local,
                  fs.target_timezone,
                  fs.forecast_daily_max_c, fs.forecast_daily_max_f,
                  fs.forecast_daily_min_c, fs.forecast_daily_min_f,
                  fs.hour_count_used
           FROM forecast_snapshots fs
           ORDER BY fs.target_date_local DESC, fs.snapshot_time_utc DESC'''
    )]
    stats = dict(conn.execute(
        '''SELECT
             COUNT(*) AS snapshot_count,
             COUNT(DISTINCT station_code) AS station_count,
             COUNT(DISTINCT source_id) AS source_count,
             MIN(target_date_local) AS first_target_date,
             MAX(target_date_local) AS last_target_date,
             MIN(snapshot_time_utc) AS first_snapshot_time_utc,
             MAX(snapshot_time_utc) AS last_snapshot_time_utc
           FROM forecast_snapshots'''
    ).fetchone())
    bundle = {
        'generated_at_utc': utc_now_iso(),
        'stations': stations,
        'sources': sources,
        'rows': rows,
        'stats': stats,
    }
    (WEB_DIR / 'data.json').write_text(json.dumps(bundle, ensure_ascii=False), encoding='utf-8')


def build_dashboard_html() -> None:
    html = '''<!doctype html>
<html><head><meta charset="utf-8"><title>Forecast Snapshot Tracker</title>
<style>
body{font-family:Arial,sans-serif;margin:20px;background:#111;color:#eee}
select,input,button{margin-right:10px;padding:6px;background:#1c1c1c;color:#eee;border:1px solid #444}
button{cursor:pointer}
label{margin-right:12px}
table{border-collapse:collapse;width:100%;margin-top:16px}
th,td{border:1px solid #444;padding:8px;text-align:left;vertical-align:top}
th{background:#222;position:sticky;top:0}
tr:nth-child(even){background:#181818}
.meta,.submeta{color:#aaa;margin-bottom:10px}
.warn{color:#f7b955}
.card{background:#181818;border:1px solid #333;padding:12px;margin:12px 0;border-radius:8px}
.small{font-size:12px;color:#aaa}
.diff-cell{background:#7a4a12 !important}
.range-cell{background:#1f6f3e !important}
.hidden-row{display:none}
.info-wrap{display:inline-block;position:relative;margin-left:6px}
.info-icon{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:50%;border:1px solid #777;color:#ddd;font-size:11px;line-height:1;cursor:help}
.tooltip{display:none;position:absolute;top:20px;left:0;background:#0f0f0f;border:1px solid #444;border-radius:8px;padding:10px;min-width:220px;max-width:320px;z-index:20;box-shadow:0 4px 14px rgba(0,0,0,.4)}
.info-wrap:hover .tooltip{display:block}
.tooltip-title{font-weight:bold;margin-bottom:6px}
.tooltip ul{margin:0;padding-left:18px}
.tooltip li{margin:2px 0}
</style></head><body>
<h1>Forecast Snapshot Tracker</h1>
<div class="meta" id="meta">Loading…</div>
<div class="submeta" id="submeta"></div>
<div class="card">
<label>Station <select id="station"></select></label>
<label>Target date <select id="targetDate"></select></label>
<button id="unitToggle">°C / °F</button>
<button id="diffToggle">Sadece Fark: Kapalı</button>
<label>Min <input id="rangeMin" type="number" step="any" placeholder="min"></label>
<label>Max <input id="rangeMax" type="number" step="any" placeholder="max"></label>
</div>
<table id="tbl"><thead></thead><tbody></tbody></table>
<script>
function fmtLocal(iso, tz){
  try {
    return new Date(iso).toLocaleString('en-GB', { timeZone: tz, year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', second:'2-digit' });
  } catch (e) {
    return iso;
  }
}
async function main(){
  const data = await fetch('./data.json').then(r=>r.json());
  const stats = data.stats || {};
  document.getElementById('meta').textContent = `Generated: ${data.generated_at_utc} | Snapshots: ${stats.snapshot_count ?? data.rows.length} | Stations: ${stats.station_count ?? data.stations.length} | Sources: ${stats.source_count ?? data.sources.length}`;
  document.getElementById('submeta').textContent = `Target-date coverage: ${stats.first_target_date || '—'} → ${stats.last_target_date || '—'} | Snapshot coverage: ${stats.first_snapshot_time_utc || '—'} → ${stats.last_snapshot_time_utc || '—'}`;
  const stationSel = document.getElementById('station');
  const dateSel = document.getElementById('targetDate');
  const unitToggle = document.getElementById('unitToggle');
  const diffToggle = document.getElementById('diffToggle');
  const rangeMin = document.getElementById('rangeMin');
  const rangeMax = document.getElementById('rangeMax');
  const stations = data.stations.map(s=>({code:s.station_code,label:`${s.city_label} (${s.station_code})`, city:s.city_label, timezone:s.timezone, country:s.country}));
  const stationMap = Object.fromEntries(stations.map(s=>[s.code, s]));
  const noaaStations = stations.filter(s => s.country === 'US').map(s => `${s.city} (${s.code})`);
  let unit = 'c';
  let onlyDiff = false;
  stations.forEach(s=>{ const o=document.createElement('option'); o.value=s.code; o.textContent=s.label; stationSel.appendChild(o); });
  function refreshDates(){
    const dates=[...new Set(data.rows.filter(r=>r.station_code===stationSel.value).map(r=>r.target_date_local))].sort().reverse();
    const prev=dateSel.value;
    dateSel.innerHTML='';
    dates.forEach(d=>{const o=document.createElement('option');o.value=d;o.textContent=d;dateSel.appendChild(o);});
    if(prev && dates.includes(prev)) dateSel.value=prev;
    render();
  }
  function numericValue(row){
    if(!row) return null;
    return unit === 'c' ? row.forecast_daily_max_c : row.forecast_daily_max_f;
  }
  function inRange(value){
    if(value === null || value === undefined) return false;
    const minRaw = rangeMin.value.trim();
    const maxRaw = rangeMax.value.trim();
    const min = minRaw === '' ? null : Number(minRaw);
    const max = maxRaw === '' ? null : Number(maxRaw);
    if(min !== null && value < min) return false;
    if(max !== null && value > max) return false;
    return min !== null || max !== null;
  }
  function render(){
    const station = stationMap[stationSel.value];
    const filtered = data.rows.filter(r=>r.station_code===stationSel.value && r.target_date_local===dateSel.value);
    const sourceIds = data.sources.map(s=>s.source_id);
    const sourceNames = Object.fromEntries(data.sources.map(s=>[s.source_id,s.display_name]));
    const grouped = {};
    filtered.forEach(r=>{ grouped[r.snapshot_time_utc] ||= {}; grouped[r.snapshot_time_utc][r.source_id]=r; });
    const times = Object.keys(grouped).sort().reverse();
    const unitLabel = unit === 'c' ? 'max °C' : 'max °F';
    document.querySelector('#tbl thead').innerHTML = '<tr><th>Snapshot time (UTC)</th><th>Snapshot time (station local)</th>' + sourceIds.map(id=>{
      const name = sourceNames[id];
      if (id === 'nws_noaa') {
        const items = noaaStations.map(x => `<li>${x}</li>`).join('');
        return `<th>${name}<span class="info-wrap"><span class="info-icon">i</span><span class="tooltip"><div class="tooltip-title">NOAA şu şehir/stationlar için kullanılıyor:</div><ul>${items}</ul></span></span><br><span class="small">${unitLabel}</span></th>`;
      }
      return `<th>${name}<br><span class="small">${unitLabel}</span></th>`;
    }).join('') + '</tr>';
    let prevValues = null;
    document.querySelector('#tbl tbody').innerHTML = times.map(ts=>{
      const currentValues = sourceIds.map(id=> numericValue(grouped[ts][id]));
      const changedFlags = currentValues.map((val, idx) => {
        if (val === null || val === undefined) return false;
        if (!prevValues) return false;
        const prev = prevValues[idx];
        if (prev === null || prev === undefined) return false;
        return val !== prev;
      });
      const rowHasDiff = changedFlags.some(Boolean);
      const hiddenClass = onlyDiff && prevValues && !rowHasDiff ? 'hidden-row' : '';
      const cols = sourceIds.map((id, idx)=>{
        const row = grouped[ts][id];
        const value = currentValues[idx];
        if(value === null || value === undefined) return '<td class="warn">—</td>';
        let cls = '';
        if(changedFlags[idx]) cls = 'diff-cell';
        if(inRange(value)) cls = 'range-cell';
        return `<td class="${cls}">${value.toFixed(2)}</td>`;
      }).join('');
      prevValues = currentValues;
      return `<tr class="${hiddenClass}"><td>${ts}</td><td>${fmtLocal(ts, station.timezone)}</td>${cols}</tr>`;
    }).join('');
    unitToggle.textContent = unit === 'c' ? '°C / °F (Şu an: °C)' : '°C / °F (Şu an: °F)';
    diffToggle.textContent = onlyDiff ? 'Sadece Fark: Açık' : 'Sadece Fark: Kapalı';
  }
  stationSel.addEventListener('change', refreshDates);
  dateSel.addEventListener('change', render);
  unitToggle.addEventListener('click', () => { unit = unit === 'c' ? 'f' : 'c'; render(); });
  diffToggle.addEventListener('click', () => { onlyDiff = !onlyDiff; render(); });
  rangeMin.addEventListener('input', render);
  rangeMax.addEventListener('input', render);
  if(stations.length){ stationSel.value=stations[0].code; refreshDates(); if(!dateSel.value){ render(); } }
}
main();
</script></body></html>'''
    (WEB_DIR / 'index.html').write_text(html, encoding='utf-8')


def run_once() -> dict:
    ensure_dirs()
    conn = connect(DB_PATH)
    upsert_metadata(conn)
    started_at = utc_now_iso()
    run_id = conn.execute(
        'INSERT INTO snapshot_runs(started_at_utc, status, error_summary) VALUES(?,?,?)',
        (started_at, 'running', ''),
    ).lastrowid
    errors: list[str] = []
    try:
        stations = load_stations()
        sources = load_sources()
        snapshot_time = utc_now_iso()
        inserted = 0
        for station in stations:
            for source in sources:
                try:
                    result = fetch_source(source.source_id, station.latitude, station.longitude, station.country)
                    if result is None:
                        continue
                    write_raw_payload(run_id, station.station_code, source.source_id, result.payload, result.status_code, snapshot_time, conn)
                    summaries = summarize_hourly_maxes(result.times, result.temperatures_c, station.timezone, max_days=6)
                    for summary in summaries:
                        conn.execute(
                            '''INSERT INTO forecast_snapshots(
                                 run_id, snapshot_time_utc, station_code, source_id, target_date_local, target_timezone,
                                 forecast_daily_max_c, forecast_daily_max_f, forecast_daily_min_c, forecast_daily_min_f,
                                 hour_count_used, created_at_utc)
                               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                            (
                                run_id,
                                snapshot_time,
                                station.station_code,
                                source.source_id,
                                summary.target_date_local,
                                summary.target_timezone,
                                summary.forecast_daily_max_c,
                                summary.forecast_daily_max_f,
                                summary.forecast_daily_min_c,
                                summary.forecast_daily_min_f,
                                summary.hour_count_used,
                                snapshot_time,
                            ),
                        )
                        inserted += 1
                    conn.commit()
                except Exception as exc:
                    errors.append(f'{station.station_code}/{source.source_id}: {exc}')
                    conn.commit()
        build_dashboard_json(conn)
        build_dashboard_html()
        status = 'ok' if not errors else 'partial'
        conn.execute(
            'UPDATE snapshot_runs SET finished_at_utc=?, status=?, error_summary=? WHERE run_id=?',
            (utc_now_iso(), status, '\n'.join(errors[:50]), run_id),
        )
        conn.commit()
        return {'run_id': run_id, 'status': status, 'inserted': inserted, 'errors': errors}
    except Exception:
        tb = traceback.format_exc()
        conn.execute(
            'UPDATE snapshot_runs SET finished_at_utc=?, status=?, error_summary=? WHERE run_id=?',
            (utc_now_iso(), 'error', tb, run_id),
        )
        conn.commit()
        raise
    finally:
        conn.close()
