from collections import Counter

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from opensky.airports import AIRPORTS
from opensky.client import OpenSkyClient


class AirlineCount(BaseModel):
    prefix: str
    count: int


class AirportTrafficResult(BaseModel):
    icao: str
    aircraft_on_ground: int
    aircraft_airborne: int
    total: int
    top_airlines: list[AirlineCount]


def register(mcp: FastMCP, client: OpenSkyClient) -> None:

    @mcp.tool()
    async def get_airport_traffic(icao: str) -> AirportTrafficResult:
        """Live snapshot of aircraft within an airport's boundary.

        Returns counts of aircraft on ground vs airborne, plus a
        breakdown by airline callsign prefix (top 5).

        icao — ICAO airport code (e.g. EGLL, VGHS). Must be in the
        supported airports list.
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

        on_ground = [s for s in states if s.on_ground]
        airborne = [s for s in states if not s.on_ground]

        prefix_counter: Counter = Counter()
        for s in states:
            if s.callsign:
                prefix = s.callsign[:3].upper()
                prefix_counter[prefix] += 1

        top_airlines = [
            AirlineCount(prefix=prefix, count=count)
            for prefix, count in prefix_counter.most_common(5)
        ]

        return AirportTrafficResult(
            icao=icao,
            aircraft_on_ground=len(on_ground),
            aircraft_airborne=len(airborne),
            total=len(states),
            top_airlines=top_airlines,
        )
