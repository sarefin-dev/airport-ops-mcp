from mcp.server.fastmcp import FastMCP

from opensky.airports import AIRPORTS, classify_congestion
from opensky.client import OpenSkyClient


def register(mcp: FastMCP, client: OpenSkyClient) -> None:

    @mcp.prompt()
    async def congestion_check(icao: str) -> str:
        """Current traffic density at an airport with recommended ground actions.

        Fetches live aircraft counts within the airport boundary and produces
        a structured assessment template for ops decision-making.

        icao — ICAO airport code (e.g. OMDB, EDDF).
        """
        icao = icao.upper()

        bbox = AIRPORTS.get(icao)
        if bbox is None:
            return (
                f"Airport {icao} is not in the supported list. "
                f"Supported airports: {', '.join(sorted(AIRPORTS))}"
            )

        try:
            states = await client.get_states_in_bbox(
                bbox["lamin"], bbox["lomin"], bbox["lamax"], bbox["lomax"]
            )
            on_ground = sum(1 for s in states if s.on_ground)
            airborne = sum(1 for s in states if not s.on_ground)
            level = classify_congestion(icao, on_ground)

            airline_counts: dict[str, int] = {}
            for s in states:
                if s.callsign:
                    prefix = s.callsign[:3].upper()
                    airline_counts[prefix] = airline_counts.get(prefix, 0) + 1
            top = sorted(airline_counts.items(), key=lambda x: -x[1])[:5]
            airline_str = ", ".join(f"{p}({c})" for p, c in top) or "none"

            data_summary = (
                f"Congestion level: {level}\n"
                f"Aircraft on ground: {on_ground}\n"
                f"Aircraft airborne (boundary zone): {airborne}\n"
                f"Total in boundary: {len(states)}\n"
                f"Airline mix (top 5): {airline_str}"
            )
        except Exception as exc:
            data_summary = f"Live data unavailable: {exc}"
            level = "UNKNOWN"

        return f"""You are an airport operations intelligence assistant providing a ground operations congestion assessment.

Airport: {icao}

LIVE CONGESTION DATA
{data_summary}

---

Produce a congestion assessment covering:

1. SITUATION SUMMARY
   Describe the current traffic density in plain ops language. Is this level normal, elevated, or critical for this airport type? Provide context (e.g. typical daily peaks, shift patterns).

2. GROUND MOVEMENT IMPLICATIONS
   What does this density mean for taxiway capacity, pushback sequencing, and stand availability? Be specific to this airport's known layout constraints where possible.

3. RECOMMENDED GROUND ACTIONS
   Provide 3–5 concrete actions appropriate for a {level} congestion state. Examples: hold at gate, expedite boarding, coordinate slot management, request ground stop, activate overflow stands.

4. MONITORING TRIGGERS
   What thresholds or events should prompt re-assessment? When should the ops controller escalate?

Tone: direct, operational. This is for a ground operations controller making real-time decisions."""
