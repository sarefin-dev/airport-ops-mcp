import time
from collections import Counter, defaultdict

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from opensky.client import OpenSkyClient
from utils.units import unix_to_utc


class AirlineStats(BaseModel):
    airline_prefix: str
    flight_count: int
    busiest_hour_utc: str | None


class DelayPatternResult(BaseModel):
    icao: str
    hours_analysed: int
    total_departures: int
    flights_per_hour: float
    top_airlines: list[AirlineStats]
    busiest_hour_utc: str | None
    note: str


def register(mcp: FastMCP, client: OpenSkyClient) -> None:

    @mcp.tool()
    async def delay_pattern(icao: str, hours_back: int = 24) -> DelayPatternResult:
        """Analyse recent departure activity at an airport.

        Returns total departure count, throughput, and per-airline breakdown
        for the specified lookback window.

        Note: OpenSky departure data is batch-updated nightly. For complete
        results use hours_back values that cover yesterday's full operation
        window (e.g. hours_back=36 to cover yesterday reliably).
        The window is capped at 48 hours per OpenSky API constraints.

        icao — ICAO airport code (e.g. EGLL).
        hours_back — hours of history to analyse (1–48, default 24).
        """
        icao = icao.upper()
        hours_back = max(1, min(hours_back, 48))

        now = int(time.time())
        begin = now - hours_back * 3600

        flights = await client.get_departures(icao, begin, now)

        if not flights:
            return DelayPatternResult(
                icao=icao,
                hours_analysed=hours_back,
                total_departures=0,
                flights_per_hour=0.0,
                top_airlines=[],
                busiest_hour_utc=None,
                note=(
                    "No departure data found for this window. "
                    "OpenSky departure data is batch-updated nightly — "
                    "today's data is incomplete. Try hours_back=36 to cover yesterday."
                ),
            )

        airline_counter: Counter = Counter()
        hour_counter: Counter = Counter()
        airline_hours: dict[str, Counter] = defaultdict(Counter)

        for f in flights:
            prefix = (f.callsign[:3].upper() if f.callsign else "UNK")
            hour_ts = (f.first_seen // 3600) * 3600
            airline_counter[prefix] += 1
            hour_counter[hour_ts] += 1
            airline_hours[prefix][hour_ts] += 1

        busiest_ts = hour_counter.most_common(1)[0][0] if hour_counter else None

        top_airlines = []
        for prefix, count in airline_counter.most_common(5):
            airline_busiest = airline_hours[prefix].most_common(1)
            top_airlines.append(
                AirlineStats(
                    airline_prefix=prefix,
                    flight_count=count,
                    busiest_hour_utc=unix_to_utc(airline_busiest[0][0])
                    if airline_busiest else None,
                )
            )

        return DelayPatternResult(
            icao=icao,
            hours_analysed=hours_back,
            total_departures=len(flights),
            flights_per_hour=round(len(flights) / hours_back, 1),
            top_airlines=top_airlines,
            busiest_hour_utc=unix_to_utc(busiest_ts),
            note=(
                "OpenSky departure data is batch-updated nightly. "
                "Recent hours may be incomplete."
            ),
        )
