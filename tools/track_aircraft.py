from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from opensky.client import OpenSkyClient
from utils.units import m_to_feet, ms_to_knots


class TrackResult(BaseModel):
    icao24: str
    callsign: str | None
    origin_country: str | None
    latitude: float | None
    longitude: float | None
    altitude_ft: int | None
    velocity_kts: float | None
    heading_deg: float | None
    vertical_rate_kts: float | None
    on_ground: bool
    squawk: str | None


def register(mcp: FastMCP, client: OpenSkyClient) -> None:

    @mcp.tool()
    async def track_aircraft(
        icao24: str | None = None,
        callsign: str | None = None,
    ) -> TrackResult:
        """Locate a live aircraft by ICAO24 transponder address or callsign.

        Provide at least one of icao24 (6-char hex, e.g. '3c6444') or
        callsign (e.g. 'BG401'). icao24 is preferred — callsign lookup
        matches only the first result from OpenSky.
        """
        if icao24 is None and callsign is None:
            raise ValueError("Provide at least one of icao24 or callsign.")

        if icao24 is not None:
            state = await client.get_aircraft_state(icao24.lower())
        else:
            state = await client.get_aircraft_state_by_callsign(callsign)  # type: ignore[arg-type]

        if state is None:
            identifier = icao24 or callsign
            raise RuntimeError(
                f"No live state found for {identifier}. "
                "The aircraft may be on the ground, out of ADS-B coverage, or the identifier is incorrect."
            )

        return TrackResult(
            icao24=state.icao24,
            callsign=state.callsign,
            origin_country=state.origin_country,
            latitude=state.latitude,
            longitude=state.longitude,
            altitude_ft=m_to_feet(state.baro_altitude),
            velocity_kts=ms_to_knots(state.velocity),
            heading_deg=state.true_track,
            vertical_rate_kts=ms_to_knots(state.vertical_rate),
            on_ground=state.on_ground,
            squawk=state.squawk,
        )
