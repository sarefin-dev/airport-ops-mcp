from mcp.server.fastmcp import FastMCP

from opensky.client import OpenSkyClient
from utils.units import m_to_feet, ms_to_knots


def register(mcp: FastMCP, client: OpenSkyClient) -> None:

    @mcp.resource("aircraft://state/{icao24}")
    async def aircraft_state(icao24: str) -> str:
        """Live position, altitude, speed, and heading for a specific aircraft.

        icao24 — 6-character hex transponder address (e.g. 3c6444).
        """
        state = await client.get_aircraft_state(icao24.lower())
        if state is None:
            return f"No live state found for aircraft {icao24}. It may be on the ground or out of coverage."

        lines = [
            f"Aircraft: {state.callsign or state.icao24}  ({state.icao24})",
            f"Origin country: {state.origin_country or 'unknown'}",
            f"Position: {state.latitude}, {state.longitude}"
            if state.latitude is not None else "Position: unavailable",
            f"Altitude: {m_to_feet(state.baro_altitude)} ft"
            if state.baro_altitude is not None else "Altitude: unavailable",
            f"Speed: {ms_to_knots(state.velocity)} kts"
            if state.velocity is not None else "Speed: unavailable",
            f"Heading: {state.true_track}°"
            if state.true_track is not None else "Heading: unavailable",
            f"Vertical rate: {ms_to_knots(state.vertical_rate)} kts"
            if state.vertical_rate is not None else "Vertical rate: unavailable",
            f"On ground: {state.on_ground}",
            f"Squawk: {state.squawk or 'none'}",
        ]
        return "\n".join(lines)
