from __future__ import annotations

import json
import urllib.request

from .base import FetchResult

USER_AGENT = 'OpenClaw forecast snapshot tracker'


def fetch_nws(lat: float, lon: float) -> FetchResult:
    point_req = urllib.request.Request(
        f'https://api.weather.gov/points/{lat},{lon}',
        headers={'User-Agent': USER_AGENT},
    )
    with urllib.request.urlopen(point_req, timeout=30) as point_resp:
        point_payload = json.loads(point_resp.read().decode('utf-8'))
    forecast_hourly_url = point_payload['properties']['forecastHourly']
    hourly_req = urllib.request.Request(
        forecast_hourly_url,
        headers={'User-Agent': USER_AGENT},
    )
    with urllib.request.urlopen(hourly_req, timeout=30) as hourly_resp:
        payload = json.loads(hourly_resp.read().decode('utf-8'))
        periods = payload.get('properties', {}).get('periods', [])
        times = [p['startTime'] for p in periods]
        temps = []
        for p in periods:
            temp = p.get('temperature')
            unit = p.get('temperatureUnit', 'F')
            if temp is None:
                temps.append(None)
            elif unit == 'F':
                temps.append(round((float(temp) - 32) * 5 / 9, 3))
            else:
                temps.append(float(temp))
        return FetchResult(
            source_id='nws_noaa',
            status_code=hourly_resp.status,
            payload={'point': point_payload, 'hourly': payload},
            times=times,
            temperatures_c=temps,
        )
