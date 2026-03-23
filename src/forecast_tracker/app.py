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
select{margin-right:10px;padding:6px;background:#1c1c1c;color:#eee;border:1px solid #444}
label{margin-right:12px}
table{border-collapse:collapse;width:100%;margin-top:16px}
th,td{border:1px solid #444;padding:8px;text-align:left;vertical-align:top}
th{background:#222;position:sticky;top:0}
tr:nth-child(even){background:#181818}
.meta,.submeta{color:#aaa;margin-bottom:10px}
.warn{color:#f7b955}
.card{background:#181818;border:1px solid #333;padding:12px;margin:12px 0;border-radius:8px}
.small{font-size:12px;color:#aaa}
</style></head><body>
<h1>Forecast Snapshot Tracker</h1>
<div class="meta" id="meta">Loading…</div>
<div class="submeta" id="submeta"></div>
<div class="card">
<label>Station <select id="station"></select></label>
<label>Target date <select id="targetDate"></select></label>
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
  const stations = data.stations.map(s=>({code:s.station_code,label:`${s.city_label} (${s.station_code})`, timezone:s.timezone}));
  const stationMap = Object.fromEntries(stations.map(s=>[s.code, s]));
  stations.forEach(s=>{ const o=document.createElement('option'); o.value=s.code; o.textContent=s.label; stationSel.appendChild(o); });
  function refreshDates(){
    const dates=[...new Set(data.rows.filter(r=>r.station_code===stationSel.value).map(r=>r.target_date_local))].sort().reverse();
    const prev=dateSel.value;
    dateSel.innerHTML='';
    dates.forEach(d=>{const o=document.createElement('option');o.value=d;o.textContent=d;dateSel.appendChild(o);});
    if(prev && dates.includes(prev)) dateSel.value=prev;
    render();
  }
  function render(){
    const station = stationMap[stationSel.value];
    const filtered = data.rows.filter(r=>r.station_code===stationSel.value && r.target_date_local===dateSel.value);
    const sourceIds = data.sources.map(s=>s.source_id);
    const sourceNames = Object.fromEntries(data.sources.map(s=>[s.source_id,s.display_name]));
    const grouped = {};
    filtered.forEach(r=>{ grouped[r.snapshot_time_utc] ||= {}; grouped[r.snapshot_time_utc][r.source_id]=r; });
    const times = Object.keys(grouped).sort().reverse();
    document.querySelector('#tbl thead').innerHTML = '<tr><th>Snapshot time (UTC)</th><th>Snapshot time (station local)</th>' + sourceIds.map(id=>`<th>${sourceNames[id]}<br><span class="small">max °C / °F</span></th>`).join('') + '</tr>';
    document.querySelector('#tbl tbody').innerHTML = times.map(ts=>{
      const cols = sourceIds.map(id=>{
        const row = grouped[ts][id];
        if(!row || row.forecast_daily_max_c===null || row.forecast_daily_max_c===undefined) return '<td class="warn">—</td>';
        return `<td>${row.forecast_daily_max_c.toFixed(2)} / ${row.forecast_daily_max_f.toFixed(2)}</td>`;
      }).join('');
      return `<tr><td>${ts}</td><td>${fmtLocal(ts, station.timezone)}</td>${cols}</tr>`;
    }).join('');
  }
  stationSel.addEventListener('change', refreshDates);
  dateSel.addEventListener('change', render);
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
