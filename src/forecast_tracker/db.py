from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = '''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS stations (
  station_code TEXT PRIMARY KEY,
  city_label TEXT NOT NULL,
  lat REAL NOT NULL,
  lon REAL NOT NULL,
  timezone TEXT NOT NULL,
  country TEXT NOT NULL,
  resolution_source_url TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  source_family TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS snapshot_runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at_utc TEXT NOT NULL,
  finished_at_utc TEXT,
  status TEXT NOT NULL,
  error_summary TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS forecast_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  snapshot_time_utc TEXT NOT NULL,
  station_code TEXT NOT NULL,
  source_id TEXT NOT NULL,
  target_date_local TEXT NOT NULL,
  target_timezone TEXT NOT NULL,
  forecast_daily_max_c REAL,
  forecast_daily_max_f REAL,
  forecast_daily_min_c REAL,
  forecast_daily_min_f REAL,
  hour_count_used INTEGER NOT NULL DEFAULT 0,
  created_at_utc TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES snapshot_runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_station_target_time
  ON forecast_snapshots (station_code, target_date_local, snapshot_time_utc);
CREATE INDEX IF NOT EXISTS idx_snapshots_source
  ON forecast_snapshots (source_id);
CREATE TABLE IF NOT EXISTS raw_payloads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  station_code TEXT NOT NULL,
  source_id TEXT NOT NULL,
  fetched_at_utc TEXT NOT NULL,
  payload_path TEXT NOT NULL,
  status_code INTEGER,
  content_hash TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES snapshot_runs(run_id)
);
'''


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
