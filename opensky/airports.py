from typing import TypedDict


class BBox(TypedDict):
    lamin: float
    lomin: float
    lamax: float
    lomax: float


class Thresholds(TypedDict):
    moderate: int
    high: int


AIRPORTS: dict[str, BBox] = {
    "VGHS": {"lamin": 23.80, "lomin": 90.32, "lamax": 23.92, "lomax": 90.48},
    "EGLL": {"lamin": 51.44, "lomin": -0.55, "lamax": 51.52, "lomax": -0.35},
    "EDDF": {"lamin": 49.97, "lomin":  8.50, "lamax": 50.10, "lomax":  8.70},
    "OMDB": {"lamin": 25.19, "lomin": 55.30, "lamax": 25.33, "lomax": 55.45},
    "VHHH": {"lamin": 22.28, "lomin": 113.87, "lamax": 22.36, "lomax": 114.00},
    "YSSY": {"lamin": -33.99, "lomin": 151.10, "lamax": -33.88, "lomax": 151.25},
}

THRESHOLDS: dict[str, Thresholds] = {
    "VGHS": {"moderate":  8, "high": 15},
    "EGLL": {"moderate": 30, "high": 55},
    "EDDF": {"moderate": 25, "high": 50},
    "OMDB": {"moderate": 25, "high": 50},
    "VHHH": {"moderate": 25, "high": 50},
    "YSSY": {"moderate": 15, "high": 30},
    "default": {"moderate": 15, "high": 30},
}


def classify_congestion(icao: str, count: int) -> str:
    """Single source of truth for congestion level classification."""
    t = THRESHOLDS.get(icao.upper(), THRESHOLDS["default"])
    if count >= t["high"]:
        return "HIGH"
    if count >= t["moderate"]:
        return "MODERATE"
    return "LOW"
