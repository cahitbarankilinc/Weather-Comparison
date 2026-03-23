from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FetchResult:
    source_id: str
    status_code: int | None
    payload: dict
    times: list[str]
    temperatures_c: list[float | None]
