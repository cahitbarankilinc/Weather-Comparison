from __future__ import annotations

import json
import urllib.parse
import urllib.request

from .base import FetchResult

BASE_URL = 'https://api.open-meteo.com/v1/forecast'
MODEL_MAP = {
    'gfs': 'gfs_global',
    'ecmwf': 'ecmwf_ifs',
    'icon': 'icon_global',
}


def fetch_open_meteo(source_id: str, lat: float, lon: float, forecast_days: int = 6) -> FetchResult:
    model = MODEL_MAP[source_id]
    query = urllib.parse.urlencode({
        'latitude': lat,
        'longitude': lon,
        'hourly': 'temperature_2m',
        'forecast_days': forecast_days,
        'timezone': 'GMT',
        'models': model,
    })
    req = urllib.request.Request(
        f'{BASE_URL}?{query}',
        headers={'User-Agent': 'OpenClaw forecast snapshot tracker'},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode('utf-8'))
        hourly = payload.get('hourly', {})
        return FetchResult(
            source_id=source_id,
            status_code=response.status,
            payload=payload,
            times=hourly.get('time', []),
            temperatures_c=hourly.get('temperature_2m', []),
        )
