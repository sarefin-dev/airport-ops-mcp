import asyncio
import json
import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv

from opensky.types import Flight, StateVector
from utils.cache import TTLCache

load_dotenv()

TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network"
    "/protocol/openid-connect/token"
)
BASE_URL = "https://opensky-network.org/api"


class TokenManager:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        async with self._lock:
            if self._token is None or time.monotonic() > self._expires_at - 60:
                await self._refresh()
            return self._token  # type: ignore[return-value]

    async def _refresh(self) -> None:
        try:
            async with httpx.AsyncClient() as http:
                r = await http.post(
                    TOKEN_URL,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                    },
                    timeout=15,
                )
                r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"OpenSky token refresh failed: HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"OpenSky token refresh network error: {exc}") from exc

        payload = r.json()
        self._token = payload["access_token"]
        self._expires_at = time.monotonic() + payload.get("expires_in", 1800)


class OpenSkyClient:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self._tokens = TokenManager(client_id, client_secret)
        self._cache = TTLCache()

    async def _get(self, endpoint: str, params: dict[str, Any], ttl: int) -> Any:
        cache_key = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        token = await self._tokens.get_token()
        try:
            async with httpx.AsyncClient() as http:
                r = await http.get(
                    f"{BASE_URL}{endpoint}",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=30,
                )
        except httpx.RequestError as exc:
            raise RuntimeError(f"OpenSky network error: {exc}") from exc

        if r.status_code == 404:
            return []
        if r.status_code == 429:
            wait = r.headers.get("X-Rate-Limit-Retry-After-Seconds", "60")
            raise RuntimeError(f"OpenSky rate limited — retry in {wait}s")
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"OpenSky API error: HTTP {exc.response.status_code}"
            ) from exc

        data = r.json()
        await self._cache.set(cache_key, data, ttl)
        return data

    def _parse_state(self, row: list) -> StateVector:
        return StateVector(
            icao24=row[0],
            callsign=row[1].strip() if row[1] else None,
            origin_country=row[2],
            longitude=row[5],
            latitude=row[6],
            baro_altitude=row[7],
            on_ground=row[8],
            velocity=row[9],
            true_track=row[10],
            vertical_rate=row[11],
            squawk=row[14],
        )

    def _parse_flight(self, f: dict) -> Flight:
        return Flight(
            icao24=f["icao24"],
            first_seen=f["firstSeen"],
            est_departure_airport=f.get("estDepartureAirport"),
            last_seen=f["lastSeen"],
            est_arrival_airport=f.get("estArrivalAirport"),
            callsign=(f.get("callsign") or "").strip() or None,
            est_departure_airport_horiz_distance=f.get("estDepartureAirportHorizDistance"),
            est_departure_airport_vert_distance=f.get("estDepartureAirportVertDistance"),
            est_arrival_airport_horiz_distance=f.get("estArrivalAirportHorizDistance"),
            est_arrival_airport_vert_distance=f.get("estArrivalAirportVertDistance"),
            departure_airport_candidates_count=f.get("departureAirportCandidatesCount", 0),
            arrival_airport_candidates_count=f.get("arrivalAirportCandidatesCount", 0),
        )

    async def get_aircraft_state(self, icao24: str) -> StateVector | None:
        data = await self._get("/states/all", {"icao24": icao24.lower()}, ttl=10)
        if not data or not data.get("states"):
            return None
        return self._parse_state(data["states"][0])

    async def get_aircraft_state_by_callsign(self, callsign: str) -> StateVector | None:
        data = await self._get(
            "/states/all", {"callsign": callsign.upper().ljust(8)}, ttl=10
        )
        if not data or not data.get("states"):
            return None
        return self._parse_state(data["states"][0])

    async def get_states_in_bbox(
        self, lamin: float, lomin: float, lamax: float, lomax: float
    ) -> list[StateVector]:
        data = await self._get(
            "/states/all",
            {"lamin": lamin, "lomin": lomin, "lamax": lamax, "lomax": lomax},
            ttl=30,
        )
        if not data or not data.get("states"):
            return []
        return [self._parse_state(row) for row in data["states"]]

    async def get_departures(self, icao: str, begin: int, end: int) -> list[Flight]:
        data = await self._get(
            "/flights/departure",
            {"airport": icao.upper(), "begin": begin, "end": end},
            ttl=300,
        )
        if not data:
            return []
        return [self._parse_flight(f) for f in data]

    async def get_arrivals(self, icao: str, begin: int, end: int) -> list[Flight]:
        data = await self._get(
            "/flights/arrival",
            {"airport": icao.upper(), "begin": begin, "end": end},
            ttl=300,
        )
        if not data:
            return []
        return [self._parse_flight(f) for f in data]

    async def get_aircraft_history(
        self, icao24: str, begin: int, end: int
    ) -> list[Flight]:
        data = await self._get(
            "/flights/aircraft",
            {"icao24": icao24.lower(), "begin": begin, "end": end},
            ttl=120,
        )
        if not data:
            return []
        return [self._parse_flight(f) for f in data]
