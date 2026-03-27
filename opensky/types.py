from dataclasses import dataclass


@dataclass
class StateVector:
    icao24: str
    callsign: str | None
    origin_country: str | None
    longitude: float | None
    latitude: float | None
    baro_altitude: float | None  # metres
    on_ground: bool
    velocity: float | None       # m/s
    true_track: float | None     # degrees from north
    vertical_rate: float | None  # m/s, negative = descending
    squawk: str | None


@dataclass
class Flight:
    icao24: str
    first_seen: int
    est_departure_airport: str | None
    last_seen: int
    est_arrival_airport: str | None
    callsign: str | None
    est_departure_airport_horiz_distance: int | None
    est_departure_airport_vert_distance: int | None
    est_arrival_airport_horiz_distance: int | None
    est_arrival_airport_vert_distance: int | None
    departure_airport_candidates_count: int
    arrival_airport_candidates_count: int
