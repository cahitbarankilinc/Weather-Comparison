from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / 'config'
DATA_DIR = PROJECT_ROOT / 'data'
RAW_PAYLOAD_DIR = DATA_DIR / 'raw_payloads'
WEB_DIR = PROJECT_ROOT / 'web'
DB_PATH = DATA_DIR / 'forecast_tracker.sqlite'


@dataclass(frozen=True)
class Station:
    city_label: str
    station_code: str
    latitude: float
    longitude: float
    timezone: str
    country: str
    resolution_source_url: str
    enabled: bool = True


@dataclass(frozen=True)
class SourceDef:
    source_id: str
    display_name: str
    source_family: str
    enabled: bool = True
    notes: str = ''


def load_stations() -> list[Station]:
    data = json.loads((CONFIG_DIR / 'stations.json').read_text())
    return [Station(**row) for row in data if row.get('enabled', True)]


def load_sources() -> list[SourceDef]:
    data = json.loads((CONFIG_DIR / 'sources.json').read_text())
    return [SourceDef(**row) for row in data if row.get('enabled', True)]
