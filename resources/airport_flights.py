from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from opensky.client import OpenSkyClient
from utils.units import unix_to_utc


def register(mcp: FastMCP, client: OpenSkyClient) -> None:

    @mcp.resource("airport://departures/{icao}/{date}")
    async def airport_departures(icao: str, date: str) -> str:
        """Historical departures from an airport on a given date (YYYY-MM-DD).

        Note: OpenSky departure data is batch-updated nightly.
        Today's data will be incomplete — use yesterday's date for full results.
        """
        icao = icao.upper()
        begin, end = _date_to_window(date)
        flights = await client.get_departures(icao, begin, end)
        if not flights:
            return f"No departure data found for {icao} on {date}."

        lines = [f"Departures from {icao} on {date} ({len(flights)} flights):\n"]
        for f in flights:
            callsign = f.callsign or f.icao24
            dest = f.est_arrival_airport or "unknown"
            lines.append(
                f"  {callsign:<10} → {dest}  departed {unix_to_utc(f.first_seen)}"
            )
        return "\n".join(lines)

    @mcp.resource("airport://arrivals/{icao}/{date}")
    async def airport_arrivals(icao: str, date: str) -> str:
        """Historical arrivals at an airport on a given date (YYYY-MM-DD).

        Note: OpenSky arrival data is batch-updated nightly.
        Today's data will be incomplete — use yesterday's date for full results.
        """
        icao = icao.upper()
        begin, end = _date_to_window(date)
        flights = await client.get_arrivals(icao, begin, end)
        if not flights:
            return f"No arrival data found for {icao} on {date}."

        lines = [f"Arrivals at {icao} on {date} ({len(flights)} flights):\n"]
        for f in flights:
            callsign = f.callsign or f.icao24
            origin = f.est_departure_airport or "unknown"
            lines.append(
                f"  {callsign:<10} ← {origin}  arrived {unix_to_utc(f.last_seen)}"
            )
        return "\n".join(lines)


def _date_to_window(date: str) -> tuple[int, int]:
    """Convert YYYY-MM-DD to (begin_unix, end_unix) for a full UTC day."""
    dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    begin = int(dt.timestamp())
    end = begin + 86400
    return begin, end
