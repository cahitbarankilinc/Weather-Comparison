from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class DailyForecastSummary:
    target_date_local: str
    target_timezone: str
    forecast_daily_max_c: float | None
    forecast_daily_max_f: float | None
    forecast_daily_min_c: float | None
    forecast_daily_min_f: float | None
    hour_count_used: int


def c_to_f(value: float | None) -> float | None:
    if value is None:
        return None
    return round((value * 9 / 5) + 32, 3)


def summarize_hourly_maxes(times: list[str], temps_c: list[float | None], timezone_name: str, max_days: int = 6) -> list[DailyForecastSummary]:
    tz = ZoneInfo(timezone_name)
    buckets: dict[str, list[float]] = defaultdict(list)
    for ts, temp in zip(times, temps_c):
        if temp is None:
            continue
        dt = datetime.fromisoformat(ts).astimezone(tz)
        buckets[dt.date().isoformat()].append(float(temp))
    target_dates = sorted(buckets.keys())[:max_days]
    out: list[DailyForecastSummary] = []
    for target_date in target_dates:
        vals = buckets[target_date]
        mx = round(max(vals), 3) if vals else None
        mn = round(min(vals), 3) if vals else None
        out.append(DailyForecastSummary(
            target_date_local=target_date,
            target_timezone=timezone_name,
            forecast_daily_max_c=mx,
            forecast_daily_max_f=c_to_f(mx),
            forecast_daily_min_c=mn,
            forecast_daily_min_f=c_to_f(mn),
            hour_count_used=len(vals),
        ))
    return out
