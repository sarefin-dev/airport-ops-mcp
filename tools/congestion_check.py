from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from opensky.airports import AIRPORTS, classify_congestion
from opensky.client import OpenSkyClient


class CongestionResult(BaseModel):
    icao: str
    level: str
    aircraft_on_ground: int
    aircraft_airborne: int
    summary: str


def register(mcp: FastMCP, client: OpenSkyClient) -> None:

    @mcp.tool()
    async def check_congestion(icao: str) -> CongestionResult:
        """Assess current traffic density at an airport using calibrated per-airport thresholds.

        Returns level (LOW / MODERATE / HIGH), aircraft counts, and a
        summary string suitable for ops briefings.

        Thresholds reflect real operational norms — EGLL at 30 aircraft on
        ground is normal; the same count at VGHS is a critical overload.

        icao — ICAO airport code. Must be in the supported airports list.
        """
        icao = icao.upper()
        bbox = AIRPORTS.get(icao)
        if bbox is None:
            raise ValueError(
                f"{icao} is not in the supported airports list. "
                f"Supported: {', '.join(sorted(AIRPORTS))}"
            )

        states = await client.get_states_in_bbox(
            bbox["lamin"], bbox["lomin"], bbox["lamax"], bbox["lomax"]
        )

        on_ground = sum(1 for s in states if s.on_ground)
        airborne = sum(1 for s in states if not s.on_ground)
        level = classify_congestion(icao, on_ground)

        summary = (
            f"{icao} is currently {level}: "
            f"{on_ground} aircraft on ground, {airborne} airborne "
            f"({len(states)} total in boundary)."
        )

        return CongestionResult(
            icao=icao,
            level=level,
            aircraft_on_ground=on_ground,
            aircraft_airborne=airborne,
            summary=summary,
        )
