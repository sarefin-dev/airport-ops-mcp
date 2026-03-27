from datetime import datetime, timezone


def ms_to_knots(v: float | None) -> float | None:
    if v is None:
        return None
    return round(v * 1.94384, 1)


def m_to_feet(v: float | None) -> int | None:
    if v is None:
        return None
    return round(v * 3.28084)


def unix_to_utc(ts: int | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
