import time
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from opensky.client import OpenSkyClient


def register(mcp: FastMCP, client: OpenSkyClient) -> None:

    @mcp.prompt()
    async def departure_brief(icao: str, date: str = "") -> str:
        """Generate an operational departure briefing for an airport.

        Fetches live congestion and recent departure pattern data, then
        produces a structured ops briefing template for Claude to complete.

        icao — ICAO airport code (e.g. EGLL, VGHS).
        date — optional date for context (YYYY-MM-DD, defaults to today).
        """
        icao = icao.upper()
        target_date = date or datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

        try:
            congestion = await client.get_states_in_bbox(
                **_bbox_for(icao, client)
            )
            on_ground = sum(1 for s in congestion if s.on_ground)
            airborne = sum(1 for s in congestion if not s.on_ground)

            from opensky.airports import classify_congestion
            level = classify_congestion(icao, on_ground)
            congestion_summary = (
                f"Congestion level: {level} | "
                f"On ground: {on_ground} | Airborne: {airborne}"
            )
        except Exception as exc:
            congestion_summary = f"Congestion data unavailable: {exc}"

        now = int(time.time())
        try:
            flights = await client.get_departures(icao, now - 86400, now)
            dep_count = len(flights)
            airlines = {}
            for f in flights:
                prefix = f.callsign[:3].upper() if f.callsign else "UNK"
                airlines[prefix] = airlines.get(prefix, 0) + 1
            top = sorted(airlines.items(), key=lambda x: -x[1])[:5]
            top_str = ", ".join(f"{p}({c})" for p, c in top) or "none"
            dep_summary = (
                f"Departures (last 24h): {dep_count} | "
                f"Top airlines: {top_str}"
            )
        except Exception as exc:
            dep_summary = (
                f"Departure history unavailable: {exc}. "
                "Note: OpenSky departure data is batch-updated nightly."
            )

        return f"""You are an airport operations intelligence assistant providing a briefing for ground operations staff.

Airport: {icao}
Briefing date: {target_date}

LIVE DATA SNAPSHOT
{congestion_summary}
{dep_summary}

Note: OpenSky departure/arrival data is batch-updated nightly. Today's departure counts may be incomplete.

---

Produce a structured operational briefing covering the following sections:

1. TRAFFIC DENSITY ASSESSMENT
   Interpret the current congestion level in operational terms. Is this within normal parameters for this airport type? What are the implications for ground movement and sequencing?

2. DEPARTURE SCHEDULE HEALTH
   Based on the 24-hour departure count and airline mix, assess schedule health. Flag any patterns suggesting delays, bunching, or reduced throughput.

3. OPERATIONAL RISK FLAGS
   Identify any conditions from the live data that require immediate attention or monitoring.

4. RECOMMENDED ACTIONS
   Provide 2–4 concrete recommended actions for the ground ops team based on current conditions.

Tone: direct, operational. Assume the reader is a ground operations controller, not a passenger. Use aviation terminology. Flag uncertainty where data is incomplete."""


def _bbox_for(icao: str, client: OpenSkyClient) -> dict:
    from opensky.airports import AIRPORTS
    bbox = AIRPORTS.get(icao)
    if bbox is None:
        raise ValueError(f"{icao} not in supported airports list.")
    return bbox
